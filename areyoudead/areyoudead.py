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
MARGIN_MIN = 1.25       # ... but at least cal_mean * MARGIN_MIN
TOP_FRACTION = 0.25     # most-active subcarriers used for the metric

# Experimental vitals (EXPECT NOISE — amplitude micro-oscillation spectroscopy)
VITALS_WIN_S = 30.0     # analysis window
VITALS_FS = 10.0        # uniform resample rate, Hz
VITALS_EVERY_S = 2.0
BREATH_BAND = (0.10, 0.60)   # Hz  (6-36 breaths/min)
HEART_BAND = (0.80, 2.20)    # Hz  (48-132 bpm)

RAW_MAGIC = 0xC5110001
FEAT_MAGIC = 0xC5110006
HDR = "<IBBHIIbbH"      # magic,node,n_ant,n_sub,freq,seq,rssi,noise,resv
HDR_LEN = struct.calcsize(HDR)

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
        self.power = deque()       # (ts, mean amplitude) — vitals series
        self.last_pkt = 0.0
        self.turbulence = 0.0
        self.cal_samples = []
        self.cal_mean = None
        self.cal_std = None
        self.threshold = None
        self.last_metrics_pub = 0.0
        self.last_vitals_pub = 0.0

    def add_frame(self, ts, amps):
        self.last_pkt = ts
        self.frames.append((ts, amps))
        while self.frames and ts - self.frames[0][0] > WINDOW_S:
            self.frames.popleft()
        # long series of total amplitude for vitals spectroscopy
        self.power.append((ts, sum(amps) / len(amps)))
        while self.power and ts - self.power[0][0] > VITALS_WIN_S + 2:
            self.power.popleft()

    def compute_vitals(self):
        """Dominant spectral peak in breathing / heart bands (Goertzel on a
        uniformly-resampled amplitude series). Experimental by design."""
        if len(self.power) < 40:
            return None
        pts = list(self.power)
        t0, t1 = pts[0][0], pts[-1][0]
        if t1 - t0 < VITALS_WIN_S * 0.6:
            return None
        n = int((t1 - t0) * VITALS_FS)
        if n < 64:
            return None
        # linear-interp resample to a uniform grid
        series, j = [], 0
        for i in range(n):
            t = t0 + i / VITALS_FS
            while j < len(pts) - 2 and pts[j + 1][0] < t:
                j += 1
            (ta, va), (tb, vb) = pts[j], pts[j + 1]
            f = 0.0 if tb == ta else (t - ta) / (tb - ta)
            series.append(va + f * (vb - va))
        mean = sum(series) / n
        series = [(v - mean) * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)))
                  for i, v in enumerate(series)]  # detrend + Hann

        def goertzel_power(freq):
            w = 2 * math.pi * freq / VITALS_FS
            c, s0, s1, s2 = 2 * math.cos(w), 0.0, 0.0, 0.0
            for v in series:
                s0 = v + c * s1 - s2
                s2, s1 = s1, s0
            return s1 * s1 + s2 * s2 - c * s1 * s2

        def band_peak(lo, hi, step):
            powers = [(goertzel_power(lo + k * step), lo + k * step)
                      for k in range(int((hi - lo) / step) + 1)]
            total = sum(p for p, _ in powers) or 1e-12
            peak, freq = max(powers)
            conf = min(1.0, (peak / (total / len(powers))) / len(powers) * 3)
            return freq * 60.0, conf

        breath_bpm, breath_conf = band_peak(*BREATH_BAND, 0.02)
        heart_bpm, heart_conf = band_peak(*HEART_BAND, 0.05)
        # waveform for the dashboard: last 8 s, breathing-band-ish smoothing
        tail = series[-int(8 * VITALS_FS):]
        k = 5
        wave = [round(sum(tail[max(0, i - k):i + 1]) / (i - max(0, i - k) + 1), 3)
                for i in range(len(tail))][::2]
        return {"breath_bpm": round(breath_bpm, 1),
                "breath_conf": round(breath_conf, 2),
                "heart_bpm": round(heart_bpm, 1),
                "heart_conf": round(heart_conf, 2),
                "wave": wave}

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
        log(f"node {self.nid} calibrated: empty mean={m:.4f} std={sd:.4f} "
            f"-> threshold={self.threshold:.4f}")
        return True

    def reset_calibration(self):
        self.cal_samples = []
        self.cal_mean = self.cal_std = self.threshold = None


nodes = {}
start_ts = time.time()
cal_until = start_ts + CAL_S
last_life = time.time()
last_life_node = None
state = "CALIBRATING"
last_pub = 0.0


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
    global cal_until, state
    if msg.topic == "areyoudead/cmd" and msg.payload == b"calibrate":
        log("recalibration requested")
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

    if data and len(data) >= HDR_LEN:
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
        elif turb > node.threshold:
            last_life = now
            last_life_node = node.nid
        if now - node.last_metrics_pub >= 0.5:
            node.last_metrics_pub = now
            mq.publish(f"areyoudead/nodes/{node.nid}", json.dumps({
                "presence": round(turb * 100, 1),   # viewer-friendly scale
                "raw": round(turb, 4),
                "threshold": round((node.threshold or 0) * 100, 1),
                "calibrated": node.calibrated(),
                "ts": now}))
        if now - node.last_vitals_pub >= VITALS_EVERY_S:
            node.last_vitals_pub = now
            vit = node.compute_vitals()
            if vit:
                vit["ts"] = now
                mq.publish(f"areyoudead/vitals/{node.nid}", json.dumps(vit))

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
    elif now - last_pub >= 2.0:
        publish()
    if now - last_pub >= TICK_S:
        last_pub = now
