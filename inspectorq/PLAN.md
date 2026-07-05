# InspectorQ — build plan

**One-liner:** A €60 AI quality-inspection cell. A USB camera + Arduino UNO Q looks at a part,
a vision-language model decides PASS/FAIL *and explains why in plain language*, an Atech board
acts as the stack-light (green/red + TFT verdict + buzzer), and a servo flicks rejects into a bin.

**Why this wins on the judging criteria:**
- *Does it work* — every piece is proven tech glued together, no model training required.
- *Demo* — hold up a part, light goes green; hold up a bad one, light goes red, screen says
  "FAIL: label is crooked", servo swats it into the bin. Instantly legible.
- *Real-world value* — industrial AOI systems start at €10–30k. MagasinX is full of companies
  that build physical products. Walk the floor with it and ask for an LOI. Reconfiguring for a
  new product = editing a prompt, not retraining a model. That's the sales line.

---

## Architecture

```
                       OpenRouter API (vision LLM)
                              ▲ frame + prompt
                              │ JSON verdict
┌─────────────────────────────┴───────────────────────────┐
│ UNO Q — Linux side (Debian, App Lab)                    │
│   main.py loop:                                         │
│     1. grab frame (USB cam, OpenCV)                     │
│     2. trigger check (part present?)                    │
│     3. POST frame → OpenRouter → {verdict, reason}      │
│     4. publish verdict → Atech stack-light              │
│     5. bridge.call("reject") if FAIL                    │
│   WebUI: live feed + pass/fail counters + last defect   │
├──────────────────── Bridge (RPC) ───────────────────────┤
│ UNO Q — STM32 MCU side (sketch.ino)                     │
│   reject(): sweep servo paddle, return to rest          │
│   (servo timing lives HERE, never in the Python loop)   │
└──────────────┬──────────────────────────────────────────┘
               │ verdict channel (serial preferred, MQTT fallback — see below)
┌──────────────▼──────────────────────────────────────────┐
│ Atech 14-port board = STACK-LIGHT                       │
│   NeoPixel grid: green PASS / red FAIL / blue thinking  │
│   TFT: verdict + one-line reason                        │
│   Speaker: chirp on PASS, buzz on FAIL                  │
│   Button: reset counters / re-arm                       │
└─────────────────────────────────────────────────────────┘
```

## Hardware allocation

| Item | Source | Role |
|---|---|---|
| UNO Q (grab a **4 GB** one if you can pick) | Arduino table (30 avail.) | Brain: camera, VLM call, WebUI, servo MCU |
| USB webcam | Arduino table (10 avail.) | Inspection camera — mount pointing at a marked "inspection zone" |
| 1–2 servos | Arduino table (20 avail.) | Reject paddle / diverter gate |
| Atech 14-port board + NeoPixel, TFT, speaker, button | Our kit | Stack-light + operator panel |
| Atech `robot_arm` (6-joint) | **ASK ATECH ON-SITE** | Upgrade: pick the bad part off instead of servo flick |
| Atech `vl53l5cx_distance` (64-zone ToF) | ask Atech if not in our box | "Part present" trigger (better than vision-polling) |
| Separate 5 V supply / powered USB hub | ask around | Servos brown out boards; camera may need powered hub |
| Cardboard ramp/bin, tape, a "product" | scrounge | The stage. Pick a real demo part (see DEMO.md) |

## The verdict channel: Atech board ↔ UNO Q — two options

**Option A — serial (try FIRST, tonight):** the `atech` Python lib has `Board.connect()`.
If it allows live control of modules over `/dev/ttyACM*` (not just monitoring), then:
`pip install atech` on the UNO Q, plug the Atech board into the UNO Q's USB, and main.py
drives the stack-light directly. Zero custom firmware, zero WiFi coupling. **Verify tonight
on the laptop:** can a Python script connect and set NeoPixel colors live? If yes, done.

**Option B — MQTT (fallback):** mosquitto broker on the UNO Q, `paho-mqtt` in main.py.
Atech board needs a custom module (clone the `light_modules/espnow_link/` pattern → `mqtt_link/`)
doing WiFi join + PubSubClient subscribe on topic `inspectorq/verdict`. Payload:
`{"verdict":"FAIL","reason":"label crooked"}`. Known SDK quirks apply (see repo memory):
file-scope code needs a custom module via `modules_path`; avoid instance name `link`.

**⚠️ WiFi note:** OpenRouter needs internet, so the UNO Q sits on venue WiFi. If Option B,
the Atech board joins the *same* AP. This is unrelated to the ESP-NOW light show — but if we
ever run the light show the same day, remember ESP-NOW is pinned to channel 1 and can't
coexist with an AP on another channel on the same radio.

## Build phases (hackathon day, ~8 h)

| # | Time | Milestone | Definition of done |
|---|---|---|---|
| 0 | 09:00–09:30 | De-risk UNO Q | App Lab's built-in "Detect Objects on Camera" example runs with our USB cam |
| 1 | 09:30–11:00 | Vision loop | main.py: frame → OpenRouter → parsed JSON verdict printed. Test with phone-charger / any part |
| 2 | 11:00–12:00 | Stack-light | Atech board shows green/red + reason on TFT + sound, driven from main.py (Option A or B) |
| 3 | 12:00–13:00 | **DEMOABLE CORE** ✅ + lunch | End-to-end: part in → light + screen + sound out. *Everything after this is bonus* |
| 4 | 13:00–14:30 | Servo reject | Bridge `reject()` on MCU sketch; paddle flicks failed part off ramp. Separate 5 V for servo |
| 5 | 14:30–15:30 | WebUI polish | Live feed, counters, gallery of failed parts w/ reasons. This is what judges crowd around |
| 6 | 15:30–17:00 | **Sales run** | Film 30-s clip, post it, walk it to 2–3 resident companies + Arduino table, ask for LOI (see DEMO.md) |
| 7 | 17:00– | Demo drilling | Run the 90-s script 5×, freeze code, charge everything |

**Rule: after phase 3 the project is always demoable. Never break the working core for a bonus feature.**

## Trigger logic (phase 1 detail)

Don't stream frames to the VLM continuously (cost + confusing verdicts on empty scenes).
Gate the inspection:
1. **Simplest:** operator presses the Atech button → snap frame → inspect. (Also great for demo pacing.)
2. Motion/diff trigger: OpenCV frame-diff on the inspection zone > threshold → part arrived → settle 500 ms → snap.
3. ToF distance module (if we get one): object closer than X in zone → snap.

Start with 1, upgrade to 2/3 if time allows.

## Risks & fallbacks

| Risk | Fallback |
|---|---|
| Venue WiFi blocks OpenRouter / flaky | Phone hotspot. Second fallback: App Lab's on-device object-detection brick with "is the expected object present" logic (weaker but offline) |
| VLM too slow (>5 s) | Switch model (see PROMPT.md model table); shrink frame to 512 px before upload |
| `Board.connect()` can't drive modules live | Option B (MQTT custom module) — budget +1 h |
| Servo stutters / board browns out | Servo on separate 5 V, common GND; keep all servo timing on MCU. If still bad: cut servo, demo stack-light only |
| Atech board serial permission on UNO Q | Same fix as laptop: `sudo chmod 666 /dev/ttyACM0` (and on the laptop as usual) |
| Camera not recognized | Try second cam early (10 available); powered hub if underpowered |

## File layout (to be created during the build)

```
inspectorq/
  PLAN.md PROMPT.md DEMO.md CHECKLIST.md   ← these docs
  app/               ← UNO Q App Lab project (main.py, sketch.ino, assets/, app.yaml)
  stacklight/        ← Atech project for the stack-light board
  light_modules/mqtt_link/  ← only if Option B needed
```
