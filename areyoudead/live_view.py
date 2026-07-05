#!/usr/bin/env python3
"""Live terminal view of the Are You Dead? sensor stream.

Run on the laptop with the UNO Q on USB:
    adb forward tcp:1883 tcp:1883
    .venv/bin/python areyoudead/live_view.py

Shows the product state machine plus a live presence bar per node.
"""
import json
import time

import paho.mqtt.client as mqtt

BAR_FULL = 40        # presence value that fills the whole bar
STATE_ICON = {
    "ALIVE": "\033[92m● ALIVE\033[0m",
    "QUIET": "\033[93m◐ QUIET — checking on you…\033[0m",
    "ALARM": "\033[91m◉ ALARM — ARE YOU DEAD?\033[0m",
    "SENSORS_DOWN": "\033[95m✖ SENSORS DOWN\033[0m",
}

state = {}
nodes = {}


def bar(v, width=BAR_FULL):
    n = min(width, int(v / BAR_FULL * width))
    return "█" * n + "░" * (width - n)


def redraw():
    print("\033[2J\033[H", end="")  # clear screen, home cursor
    print("=== ARE YOU DEAD?  — live sensor feed ===\n")
    s = state.get("state", "?")
    print(f"  {STATE_ICON.get(s, s)}")
    print(f"  seconds since last sign of life: "
          f"{state.get('seconds_since_life', '?')}"
          f"   (quiet at {state.get('quiet_after_s', '?')}s, "
          f"alarm at {state.get('alarm_after_s', '?')}s)\n")
    for nid in sorted(nodes):
        d = nodes[nid]
        age = time.time() - d["rx"]
        status = "ONLINE " if age < 10 else "OFFLINE"
        print(f"  node {nid} [{status}] presence {d['presence']:6.1f} "
              f"|{bar(d['presence'])}|")
    print("\n  (ctrl-c to quit)")


def on_message(client, userdata, msg):
    global state
    try:
        d = json.loads(msg.payload)
    except json.JSONDecodeError:
        return
    if msg.topic == "areyoudead/state":
        state = d
    elif msg.topic.startswith("areyoudead/nodes/"):
        nid = msg.topic.rsplit("/", 1)[1]
        nodes[nid] = {"presence": d["presence"], "rx": time.time()}
    redraw()


mq = mqtt.Client(client_id="live-view")
mq.on_message = on_message
mq.connect("127.0.0.1", 1883)
mq.subscribe([("areyoudead/state", 0), ("areyoudead/nodes/#", 0)])
print("connected — waiting for data…")
mq.loop_forever()
