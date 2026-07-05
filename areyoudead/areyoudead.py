#!/usr/bin/env python3
"""Are You Dead? — aliveness watchdog, v2 (raw CSI amplitude analysis).

v1 trusted the ESP32's on-chip presence score (phase-variance based) —
measured on-site to not separate occupied from empty (ESP32 phase is
noise; community consensus is to use AMPLITUDE). v2 does the standard
thing (cf. ESPectre, esp-csi literature):

  * nodes run edge-tier 0: raw CSI frames (0xC5110001) -> UDP :5005
  * per node, keep a sliding window of per-subcarrier amplitudes
  * turbulence = mean over top quartile subcarriers of (std/mean)
    within the window — human motion makes amplitudes tremble
  * calibrate an empty-room baseline for CAL_S seconds at startup
    (or on MQTT command), threshold = baseline stats * margin
  * turbulence above threshold = sign of life

State machine (unchanged from v1):
  ALIVE -> QUIET (QUIET_S) -> ALARM (ALARM_S); SENSORS_DOWN when blind;
  sensor recovery resets the life clock. CALIBRATING while learning.

MQTT (unchanged contract + calibration extras):
  areyoudead/state     retained JSON
  areyoudead/event     transitions
  areyoudead/nodes/N   {"presence": turbulence*100, "raw": ...} ~2 Hz
  areyoudead/cmd       "calibrate" -> re-learn empty baseline
"""
import json
import math
import os
import socket
import struct
import time
from collections import deque

import paho.mqtt.client as mqtt

# ---- Tunables (env-overridable: QUIET_S=5 ALARM_S=10 for fast testing) ----
QUIET_S = float(os.environ.get("QUIET_S", 30.0))
ALARM_S = float(os.environ.get("ALARM_S", 60.0))
SENSOR_TIMEOUT_S = 10.0
TICK_S = 0.5

CAL_S = 60.0            # empty-room learning period
WINDOW_S = 6.0          # sliding window for turbulence
MARGIN_STD = 4.0        # threshold = cal_mean + MARGIN_STD * cal_std
MARGIN_MIN = 1.15       # ... but at least cal_mean * MARGIN_MIN
                        # (1.25 proved too high in the afternoon hall:
                        # empty ~0.36, walking person peaks ~0.41-0.45)
MARGIN_LO = 0.12        # low-side band: life if turb < mean*(1-MARGIN_LO)
TOP_FRACTION = 0.25     # most-active subcarriers used for the metric

RAW_MAGIC = 0xC5110001
FEAT_MAGIC = 0xC5110006
HDR = "<IBBHIIbbH"      # magic,node,n_ant,n_sub,freq,seq,rssi,noise,resv
HDR_LEN = struct.calcsize(HDR)

# Only OUR boards may feed the brain. A teammate's RuView nodes joined the
# hotspot with node-ids 1/2 and their 20 m CSI path turned our baseline to
# mush. Kernel has no netfilter, so we check sender MAC (via ARP) here.
ALLOWED_MACS = {"9c:13:9e:19:01:68", "9c:13:9e:19:f3:0c"}
_allowed_ips = set()
_denied_ips = {}                # ip -> last ARP re-check ts


def sender_allowed(ip):
    if ip in _allowed_ips:
        return True
    now = time.time()
    if now - _denied_ips.get(ip, 0) < 30.0:
        return False
    _denied_ips[ip] = now
    try:
        with open("/proc/net/arp") as f:
            for line in f.readlines()[1:]:
                cols = line.split()
                if cols[0] == ip and cols[3].lower() in ALLOWED_MACS:
                    _allowed_ips.add(ip)
                    return True
    except OSError:
        pass
    log(f"DROPPING packets from unauthorized sender {ip}")
    return False


# ---------------------------------------------------------------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))
sock.settimeout(TICK_S)

mq = mqtt.Client(client_id="areyoudead-brain")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Node:
    def __init__(self, nid):
        self.nid = nid
        self.frames = deque()      # (ts, [amplitude per subcarrier])
        self.last_pkt = 0.0
        self.turbulence = 0.0
        self.cal_samples = []
        self.cal_mean = None
        self.cal_std = None
        self.threshold = None
        self.threshold_lo = None
        self.last_metrics_pub = 0.0

    def add_frame(self, ts, amps):
        self.last_pkt = ts
        self.frames.append((ts, amps))
        while self.frames and ts - self.frames[0][0] > WINDOW_S:
            self.frames.popleft()

    def compute_turbulence(self):
        if len(self.frames) < 10:
            return None
        n_sub = min(len(a) for _, a in self.frames)
        ratios = []
        frames = list(self.frames)
        for k in range(n_sub):
            vals = [a[k] for _, a in frames]
            m = sum(vals) / len(vals)
            if m < 1e-6:
                continue
            var = sum((v - m) ** 2 for v in vals) / len(vals)
            ratios.append(math.sqrt(var) / m)
        if not ratios:
            return None
        ratios.sort(reverse=True)
        top = ratios[:max(1, int(len(ratios) * TOP_FRACTION))]
        self.turbulence = sum(top) / len(top)
        return self.turbulence

    def calibrated(self):
        return self.threshold is not None

    def feed_calibration(self, turb):
        self.cal_samples.append(turb)

    def finish_calibration(self):
        if len(self.cal_samples) < 10:
            return False
        m = sum(self.cal_samples) / len(self.cal_samples)
        var = sum((v - m) ** 2 for v in self.cal_samples) / len(self.cal_samples)
        sd = math.sqrt(var)
        self.cal_mean, self.cal_std = m, sd
        self.threshold = max(m + MARGIN_STD * sd, m * MARGIN_MIN)
        # a body ON the AP-node path can ABSORB multipath -> turbulence
        # DROPS below the empty baseline (seen live in the empty hall);
        # deviation in either direction is a sign of life
        self.threshold_lo = m - max(MARGIN_STD * sd, m * MARGIN_LO)
        log(f"node {self.nid} calibrated: empty mean={m:.4f} std={sd:.4f} "
            f"-> threshold={self.threshold:.4f}/lo={self.threshold_lo:.4f}")
        save_calibration()
        return True

    def reset_calibration(self):
        self.cal_samples = []
        self.cal_mean = self.cal_std = None
        self.threshold = self.threshold_lo = None


nodes = {}
start_ts = time.time()
last_life = time.time()
last_life_node = None
last_pub = 0.0
last_state_pub = 0.0

# ---- calibration persistence: survive restarts, re-learn only on demand ----
CAL_FILE = "/home/arduino/calibration.json"


def save_calibration():
    data = {str(n.nid): {"cal_mean": n.cal_mean, "cal_std": n.cal_std,
                         "threshold": n.threshold,
                         "threshold_lo": n.threshold_lo}
            for n in nodes.values() if n.calibrated()}
    if data:
        with open(CAL_FILE, "w") as f:
            json.dump(data, f)
        log(f"calibration saved to {CAL_FILE}: "
            + ", ".join(f"n{k} thr={v['threshold']:.3f}" for k, v in data.items()))


def load_calibration():
    try:
        with open(CAL_FILE) as f:
            return {int(k): v for k, v in json.load(f).items()}
    except (OSError, ValueError):
        return {}


saved_cal = load_calibration()
if saved_cal:
    cal_until = start_ts          # no learning period: arm from saved baseline
    state = "ALIVE"
    log("loaded saved calibration: "
        + ", ".join(f"n{k} thr={v['threshold']:.3f}" for k, v in saved_cal.items()))
else:
    cal_until = start_ts + CAL_S
    state = "CALIBRATING"


def publish(event=None):
    now = time.time()
    online = {str(n): (now - v.last_pkt <= SENSOR_TIMEOUT_S)
              for n, v in nodes.items()}
    payload = {
        "state": state,
        "seconds_since_life": round(now - last_life, 1),
        "last_life_node": last_life_node,
        "nodes_online": online,
        "quiet_after_s": QUIET_S,
        "alarm_after_s": ALARM_S,
        "calibrating_for_s": round(max(0.0, cal_until - now), 1),
        "ts": now,
    }
    mq.publish("areyoudead/state", json.dumps(payload), retain=True)
    if event:
        mq.publish("areyoudead/event", json.dumps({"event": event, **payload}))
        log(f"EVENT: {event} ({payload['seconds_since_life']}s since life)")


def on_mqtt_message(client, userdata, msg):
    global cal_until, state, saved_cal
    if msg.topic == "areyoudead/cmd" and msg.payload == b"calibrate":
        log("recalibration requested")
        saved_cal = {}   # else the boot-restore path re-applies stale
                         # baselines at the window boundary (race)
        for n in nodes.values():
            n.reset_calibration()
        cal_until = time.time() + CAL_S


mq.on_message = on_mqtt_message
mq.connect("127.0.0.1", 1883)
mq.subscribe("areyoudead/cmd")
mq.loop_start()

log(f"Are You Dead? brain v2 (raw CSI) starting — calibrating {CAL_S:.0f}s, "
    f"KEEP THE ZONE EMPTY")
publish("startup")

while True:
    try:
        data, addr = sock.recvfrom(4096)
    except socket.timeout:
        data = None

    now = time.time()

    if data and len(data) >= HDR_LEN and sender_allowed(addr[0]):
        magic = struct.unpack_from("<I", data)[0]
        if magic == RAW_MAGIC:
            (m, nid, n_ant, n_sub, freq, seq,
             rssi, noise, _r) = struct.unpack_from(HDR, data)
            need = HDR_LEN + n_ant * n_sub * 2
            if 0 < n_sub <= 512 and len(data) >= need:
                iq = struct.unpack_from(f"<{n_ant * n_sub * 2}b", data, HDR_LEN)
                # first antenna only; amplitude per subcarrier
                amps = [math.hypot(iq[2 * k], iq[2 * k + 1])
                        for k in range(n_sub)]
                node = nodes.setdefault(nid, Node(nid))
                # apply persisted baseline to a newly-seen node (not while a
                # fresh learning window is running)
                if (not node.calibrated() and nid in saved_cal
                        and now >= cal_until):
                    c = saved_cal[nid]
                    node.cal_mean = c["cal_mean"]
                    node.cal_std = c["cal_std"]
                    node.threshold = c["threshold"]
                    node.threshold_lo = c.get("threshold_lo",  # older files
                        c["cal_mean"] - max(MARGIN_STD * c["cal_std"],
                                            c["cal_mean"] * MARGIN_LO))
                node.add_frame(now, amps)
        elif magic == FEAT_MAGIC and len(data) == 60:
            # tier-2 stragglers: still counts as node heartbeat
            nid = struct.unpack_from("<IB", data)[1]
            nodes.setdefault(nid, Node(nid)).last_pkt = now

    # ---- periodic evaluation ----
    if now - last_pub < TICK_S and state != "CALIBRATING":
        continue

    calibrating = now < cal_until
    any_online = any(now - v.last_pkt <= SENSOR_TIMEOUT_S
                     for v in nodes.values())

    for node in nodes.values():
        turb = node.compute_turbulence()
        if turb is None:
            continue
        if calibrating:
            node.feed_calibration(turb)
        elif not node.calibrated():
            node.finish_calibration()
        elif turb > node.threshold or turb < node.threshold_lo:
            last_life = now
            last_life_node = node.nid
        if now - node.last_metrics_pub >= 0.5:
            node.last_metrics_pub = now
            mq.publish(f"areyoudead/nodes/{node.nid}", json.dumps({
                "presence": round(turb * 100, 1),   # viewer-friendly scale
                "raw": round(turb, 4),
                "threshold": round((node.threshold or 0) * 100, 1),
                "threshold_lo": round((node.threshold_lo or 0) * 100, 1),
                "calibrated": node.calibrated(),
                "ts": now}))

    if calibrating:
        new_state = "CALIBRATING"
        last_life = now              # never alarm during calibration
    elif not any_online and now - start_ts > SENSOR_TIMEOUT_S:
        new_state = "SENSORS_DOWN"
    else:
        if any_online and state == "SENSORS_DOWN":
            last_life = now
            last_life_node = None
        if state == "CALIBRATING":
            last_life = now          # life clock starts after learning
        quiet_for = now - last_life
        if quiet_for >= ALARM_S:
            new_state = "ALARM"
        elif quiet_for >= QUIET_S:
            new_state = "QUIET"
        else:
            new_state = "ALIVE"

    if new_state != state:
        old, state = state, new_state
        publish(f"{old}->{state}")
        last_state_pub = now
    elif now - last_state_pub >= 1.0:
        publish()
        last_state_pub = now
    if now - last_pub >= TICK_S:
        last_pub = now
