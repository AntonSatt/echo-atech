#!/usr/bin/env python3
"""Are You Dead? — aliveness watchdog for RuView CSI sensor nodes.

Listens for feature-state packets (0xC5110006) on UDP :5005, tracks the
last sign of life (motion/presence), and walks a state machine:

    ALIVE  -> QUIET  (no life signs for QUIET_S seconds)
    QUIET  -> ALARM  (still nothing at ALARM_S seconds)
    any    -> ALIVE  (any fresh life sign)
    SENSORS_DOWN     (no packets at all from any node -- system fault,
                      never to be confused with "person not moving")

State is published to MQTT (localhost) for dashboards / the Atech
light-show alarm bridge:
    areyoudead/state   retained JSON, republished every tick
    areyoudead/event   transition events only
"""
import json
import socket
import struct
import time

import paho.mqtt.client as mqtt

# ---- Tunables (demo-friendly defaults) ------------------------------------
QUIET_S = 30.0          # no life signs for this long -> QUIET ("checking in")
ALARM_S = 60.0          # -> ALARM (in the real product: minutes/hours)
SENSOR_TIMEOUT_S = 10.0  # node silent this long = offline
MOTION_LIFE = 0.5        # motion_score above this counts as life
PRESENCE_LIFE = 0.5      # presence_score above this counts as life
TICK_S = 0.5

FEAT_MAGIC = 0xC5110006
FMT = "<IBBHQ9fHHI"  # magic,node,mode,seq,ts_us,9 floats,qflags,resv,crc

# ---------------------------------------------------------------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))
sock.settimeout(TICK_S)

mq = mqtt.Client(client_id="areyoudead-brain")
mq.connect("127.0.0.1", 1883)
mq.loop_start()

nodes = {}            # node_id -> {last_pkt, presence, motion}
start_ts = time.time()
last_life = time.time()   # start optimistic: booting != dead
last_life_node = None
state = "ALIVE"
last_pub = 0.0


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def publish(event=None):
    now = time.time()
    online = {str(n): (now - v["last_pkt"] <= SENSOR_TIMEOUT_S)
              for n, v in nodes.items()}
    payload = {
        "state": state,
        "seconds_since_life": round(now - last_life, 1),
        "last_life_node": last_life_node,
        "nodes_online": online,
        "quiet_after_s": QUIET_S,
        "alarm_after_s": ALARM_S,
        "ts": now,
    }
    mq.publish("areyoudead/state", json.dumps(payload), retain=True)
    if event:
        mq.publish("areyoudead/event", json.dumps({"event": event, **payload}))
        log(f"EVENT: {event} ({payload['seconds_since_life']}s since life)")


log(f"Are You Dead? brain starting (quiet={QUIET_S}s alarm={ALARM_S}s)")
publish("startup")

while True:
    try:
        data, addr = sock.recvfrom(4096)
    except socket.timeout:
        data = None

    now = time.time()

    if data and len(data) == 60:
        fields = struct.unpack(FMT, data)
        if fields[0] == FEAT_MAGIC:
            node, motion, presence = fields[1], fields[5], fields[6]
            nodes[node] = {"last_pkt": now, "presence": presence,
                           "motion": motion}
            if motion > MOTION_LIFE or presence > PRESENCE_LIFE:
                last_life = now
                last_life_node = node

    any_online = any(now - v["last_pkt"] <= SENSOR_TIMEOUT_S
                     for v in nodes.values())

    # Sensors just came back after being blind: restart the life clock,
    # we cannot claim anything about the blind interval.
    if any_online and state == "SENSORS_DOWN":
        last_life = now
        last_life_node = None

    quiet_for = now - last_life

    # No sensors online -- system is blind. Never report ALIVE on no data:
    # "my sensors are dead" must be distinguishable from "the person is fine".
    if not any_online and now - start_ts > SENSOR_TIMEOUT_S:
        new_state = "SENSORS_DOWN"
    elif quiet_for >= ALARM_S:
        new_state = "ALARM"
    elif quiet_for >= QUIET_S:
        new_state = "QUIET"
    else:
        new_state = "ALIVE"

    if new_state != state:
        old, state = state, new_state
        publish(f"{old}->{state}")
    elif now - last_pub >= 2.0:
        publish()
        last_pub = now
