#!/usr/bin/env python3
"""Are You Dead? — SMS alert bridge (46elks).

Runs on the LAPTOP, not the UNO Q: the brain's radio hosts the sensor
hotspot, so the brain has no internet. The laptop has venue WiFi and
reaches the broker through `adb forward tcp:1883 tcp:1883`.

    [brain MQTT areyoudead/event] --> this script --> 46elks SMS API

Alerts (each with its own cooldown so a flapping demo doesn't drain credits):
  * -> ALARM         "no signs of life for Xs"  (also fired if we attach
                      while the retained state is already ALARM)
  * ALARM -> ALIVE   "signs of life again"
  * -> SENSORS_DOWN  "monitoring is blind"

Config via env, or a `sms.env` file next to this script (KEY=VALUE lines,
gitignored — put the API secret there):
  ELKS_USER / ELKS_PASS  46elks API username (u...) + API password
  SMS_TO                 recipient(s), E.164, comma-separated: +46701234567
  SMS_FROM               alphanumeric sender, max 11 chars (AreYouDead)
  SMS_DRYRUN=yes         ask 46elks to validate but not send (free)
  SMS_COOLDOWN_S         min seconds between SMS per alert type (20)
  MQTT_HOST / MQTT_PORT  broker (127.0.0.1:1883 = adb forward)

Test the credentials without waiting for an alarm:
    ./sms_alert.py --test              # real SMS
    SMS_DRYRUN=yes ./sms_alert.py --test
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import paho.mqtt.client as mqtt

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sms.env")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

ELKS_USER = os.environ.get("ELKS_USER", "")
ELKS_PASS = os.environ.get("ELKS_PASS", "")
SMS_TO = [n.strip() for n in os.environ.get("SMS_TO", "").split(",") if n.strip()]
SMS_FROM = os.environ.get("SMS_FROM", "AreYouDead")   # alnum, max 11 chars
SMS_DRYRUN = os.environ.get("SMS_DRYRUN", "").lower() in ("1", "yes", "true")
COOLDOWN_S = float(os.environ.get("SMS_COOLDOWN_S", 20.0))
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

API_URL = "https://api.46elks.com/a1/sms"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def send_sms(message):
    """POST to 46elks; returns True if every recipient was accepted."""
    ok = True
    for to in SMS_TO:
        fields = {"from": SMS_FROM, "to": to, "message": message}
        if SMS_DRYRUN:
            fields["dryrun"] = "yes"
        req = urllib.request.Request(
            API_URL, data=urllib.parse.urlencode(fields).encode())
        # basic auth by hand: HTTPBasicAuthHandler only answers 401
        # challenges and 46elks wants credentials up front
        cred = base64.b64encode(f"{ELKS_USER}:{ELKS_PASS}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode())
            log(f"SMS {'(dryrun) ' if SMS_DRYRUN else ''}to {to}: "
                f"{body.get('status', '?')} cost={body.get('cost', '?')} "
                f"— {message!r}")
        except urllib.error.HTTPError as e:
            log(f"SMS to {to} FAILED: HTTP {e.code} {e.read().decode()[:200]}")
            ok = False
        except OSError as e:
            log(f"SMS to {to} FAILED: {e}")
            ok = False
    return ok


last_sent = {}          # alert type -> ts of last SMS


def alert(kind, message):
    now = time.time()
    if now - last_sent.get(kind, 0) < COOLDOWN_S:
        log(f"suppressed {kind} (cooldown {COOLDOWN_S:.0f}s): {message!r}")
        return
    last_sent[kind] = now
    send_sms(message)


prev_state = None       # last state seen on either topic


def handle_state(new_state, payload):
    global prev_state
    old, prev_state = prev_state, new_state
    if new_state == old:
        return
    secs = payload.get("seconds_since_life", "?")
    if new_state == "ALARM":
        alert("alarm",
              f"ARE YOU DEAD? No signs of life for {secs}s in the "
              f"monitored zone. Please check on them now.")
    elif old == "ALARM" and new_state == "ALIVE":
        alert("recovery", "Signs of life again in the monitored zone. "
                          "All clear.")
    elif new_state == "SENSORS_DOWN":
        alert("sensors", "Are You Dead? sensors went offline — "
                         "monitoring is blind.")


def on_connect(client, userdata, flags, rc):
    log(f"MQTT connected (rc={rc}), watching areyoudead/event")
    client.subscribe([("areyoudead/event", 0), ("areyoudead/state", 0)])


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
    except ValueError:
        return
    if msg.topic == "areyoudead/event":
        handle_state(payload.get("state"), payload)
    elif msg.topic == "areyoudead/state" and prev_state is None:
        # first retained state: catch an ALARM already in progress
        handle_state(payload.get("state"), payload)


def main():
    if not ELKS_USER or not ELKS_PASS:
        sys.exit("set ELKS_USER + ELKS_PASS (env or sms.env next to script)")
    if not SMS_TO:
        sys.exit("set SMS_TO to at least one +46... number")

    if "--test" in sys.argv:
        ok = send_sms("Test from Are You Dead? SMS bridge. "
                      "If you can read this, alerts are live.")
        sys.exit(0 if ok else 1)

    mq = mqtt.Client(client_id="areyoudead-sms")
    mq.on_connect = on_connect
    mq.on_message = on_message
    mq.connect(MQTT_HOST, MQTT_PORT)
    log(f"SMS bridge up: to={','.join(SMS_TO)} from={SMS_FROM} "
        f"cooldown={COOLDOWN_S:.0f}s dryrun={SMS_DRYRUN}")
    mq.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
