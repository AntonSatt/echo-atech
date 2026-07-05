# InspectorQ — prep checklist

## Tonight (laptop)

- [ ] `source .venv/bin/activate && pip install paho-mqtt opencv-python requests`
- [ ] **Decisive test — Option A vs B:** can `atech`'s `Board.connect()` drive modules
      live from Python (set NeoPixel color from a script)? Plug in a board and try.
      Works → verdict channel is plain serial, no custom firmware. Doesn't → budget
      +1 h tomorrow for the `mqtt_link` custom module (clone `light_modules/espnow_link/`).
- [ ] **Vision loop dry-run on the laptop webcam:** frame → OpenRouter → JSON verdict,
      using PROMPT.md v1. Confirms the OpenRouter key, model ids, JSON parsing, and
      latency before ever touching a UNO Q. (`OPENROUTER_API_KEY` in env, never in code.)
- [ ] Benchmark the 3 shortlist models (PROMPT.md) on 3 photos: a good object, a damaged
      one, an empty scene. Note latency + verdict quality.
- [ ] `sudo usermod -aG dialout kaffe` + log out/in — kills the chmod-after-every-replug tax.
- [ ] `sudo apt install mosquitto mosquitto-clients` (only matters if Option B).
- [ ] Charge laptop + power bank; confirm phone hotspot works with the laptop.

## To bring

- [ ] Laptop + charger (organizers: everything else is provided)
- [ ] Atech boards + full module set (esp. NeoPixel, TFT, speaker, button) + cables
- [ ] Phone (hotspot fallback + filming the traction clip)
- [ ] A demo product with a photogenic failure mode: one good unit + two damageable units
      (boxed item with a label, or capped bottle). Don't rely on finding one there.
- [ ] 3 printed LOI copies (template in DEMO.md), a pen
- [ ] Tape, cardboard, zip ties if lying around (ramp + camera mount)

## First 30 minutes on-site

- [ ] Grab: 1× UNO Q (**4 GB** if there's a choice), 1× USB cam (+ a spare), 2× servos,
      USB-C dongle. Also ask Atech: **can we borrow the `robot_arm` module?** and do they
      have a `vl53l5cx_distance` ToF module? Confirm what's actually in our own kit
      (day-1 notes say PIR/no-distance; the current catalog says mic + ToF, no PIR).
- [ ] Boot UNO Q, get it on venue WiFi, run App Lab's built-in **"Detect Objects on
      Camera"** example with our USB cam. Green light on the whole vision pipeline
      before writing a line of code.
- [ ] Verify UNO Q Linux side has internet (curl openrouter.ai) — if blocked, switch to
      hotspot NOW and plan around it.
- [ ] Say hi to Karl (Arduino): mention the plan — UNO Q vision + Atech stack-light
      integration. Ask for the fastest Bridge servo example and any UNO Q camera gotchas.

## Standing rules for the day

- After the 13:00 demoable-core milestone, never break the working demo for a feature.
- Servo gets its own 5 V supply, common ground; servo timing lives on the MCU sketch only.
- Every failed part frame saves to `failures/` — that gallery is evidence for the jury.
- 15:30 sharp: stop building, start the sales run (DEMO.md). An LOI beats a feature.
- 17:00: code freeze, rehearse the 90-s script 5×.
