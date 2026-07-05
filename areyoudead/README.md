# Are You Dead? — WiFi presence dead-man's-switch

MagasinX hackathon day-2 build (2026-07-05). Inspired by the viral Chinese
"Are You Dead?" check-in app for young people living alone — except nobody
has to tap a button: the apartment's own WiFi notices whether you're alive.

**Demo loop (verified live at this checkpoint):** empty zone → `QUIET` after
30 s → `ALARM` after 60 s → person steps in → `ALIVE` in <1 s. Detection is
a little spotty at the edges but the core loop is reproducible.

## Architecture

```
[ESP32-S3 node 1]──┐  raw CSI frames        ┌─ areyoudead.py (this dir)
   RuView fw        ├──UDP :5005──▶ UNO Q ──┤  mosquitto (MQTT :1883)
[ESP32-S3 node 2]──┘   WiFi "areyoudead"    └─ (future: light-show bridge)
```

- **UNO Q "stockholm67"** (Debian, user `arduino`/`arduino1`): WiFi AP
  `areyoudead` (2.4 GHz ch 11, pw `staywithus`, 10.42.0.1), MQTT broker,
  and the watchdog brain. Everything auto-starts on boot.
- **2× Atech 14-port ESP32-S3** flashed with RuView CSI firmware
  (v0.7.0 built from source + our status-LED addon), NeoPixel grid in
  port 9 as status light: yellow=calibrating, green=sensing,
  orange=degraded, red=alert, white=booting.
- Nodes stream **raw CSI** (`--edge-tier 0`) filtered to our AP's frames
  (`--filter-mac`). The chip's own presence score (phase-based) was
  measured useless in a crowded hall; the brain computes **amplitude
  turbulence vs a learned empty-room baseline** instead (the method
  ESPectre / esp-csi deployments use).

## The brain (`areyoudead.py` on UNO Q at /home/arduino/)

- 60 s **calibration on every start — zone must be empty** (status shows
  CALIBRATING; live viewer says stay out).
- Turbulence = mean over top-quartile subcarriers of std/mean amplitude in
  a 6 s window; life = turbulence > max(cal_mean+4σ, 1.25×cal_mean).
- States: `CALIBRATING → ALIVE → QUIET → ALARM`, plus `SENSORS_DOWN`
  (sensor death is never reported as "person fine"; recovery resets clock).
- MQTT: `areyoudead/state` (retained), `areyoudead/event` (transitions),
  `areyoudead/nodes/N` (live metrics), `areyoudead/cmd` ← `"calibrate"`.
- Timings via env `QUIET_S`/`ALARM_S` (defaults 30/60). Fast test mode
  (5/10) is a systemd drop-in on the board:
  `/etc/systemd/system/areyoudead.service.d/testing.conf` — **delete it +
  `systemctl daemon-reload && systemctl restart areyoudead` to restore
  demo timings.**

## Laptop live viewer

```bash
adb forward tcp:1883 tcp:1883        # after every UNO Q USB replug
.venv/bin/python areyoudead/live_view.py
```

## Rebuild-from-nothing recipes

**Node firmware** (only if a board is lost/replaced — binaries in
`firmware-addons/` are ready to flash):

```bash
# flash everything (new/blank board), port = /dev/ttyACM* (chmod 666 it):
python -m esptool --chip esp32s3 --port PORT --baud 460800 write_flash \
  --flash_mode dio --flash_size 8MB --flash_freq 80m \
  0x0 bootloader.bin 0x8000 partition-table.bin \
  0xf000 ota_data_initial.bin 0x20000 esp32-csi-node-v0.7.0-statusled.bin
# provision (also re-run any time settings change; venv needs
# esptool pyserial esp-idf-nvs-partition-gen):
python RuView/firmware/esp32-csi-node/provision.py --port PORT \
  --ssid areyoudead --password staywithus --target-ip 10.42.0.1 \
  --target-port 5005 --node-id N --channel 11 \
  --filter-mac 14:B5:CD:F8:69:23 --edge-tier 0
```

To rebuild the binary itself: clone github.com/ruvnet/RuView, apply
`firmware-addons/ruview-hackathon.patch`, drop `status_led.{c,h}` into
`firmware/esp32-csi-node/main/`, then
`docker run --rm -v $PWD/firmware/esp32-csi-node:/project -w /project
espressif/idf:v5.4 bash -c "idf.py set-target esp32s3 && idf.py build"`
(README's v5.2 is stale and fails).

**UNO Q from factory** (full story in Claude's memory `uno-q-stockholm67`):
adb shell → `echo PW | sudo arduino-passwd` → `sudo dpkg-reconfigure
openssh-server` → `systemctl enable --now ssh` → `apt install mosquitto
mosquitto-clients python3-paho-mqtt` (needs temporary WiFi:
`nmcli dev wifi connect MagasinX password ...` — venue is 5/6 GHz-only so
ESP32s can't use it, but the UNO Q can) → hotspot:
`nmcli con add type wifi ifname wlan0 con-name areyoudead autoconnect yes
ssid areyoudead mode ap ipv4.method shared 802-11-wireless.band bg
802-11-wireless.channel 11 wifi-sec.key-mgmt wpa-psk wifi-sec.psk
staywithus` → copy `areyoudead.py` + `areyoudead.service` over, enable.

## Hard-won gotchas

- RuView's **pre-built binaries (v0.6.7) have the S3 zero-CSI-yield bug** —
  always flash our binary or build from source (self-ping fix #521/#954).
- **Power banks kill the nodes** (auto-off on low draw) — wall chargers.
- Provisioning NVS survives app-only reflash (offset 0x20000).
- Restarting the brain = new calibration = 60 s empty-zone requirement.
- Sitting perfectly still reads as no-life within ~10-60 s — that's the
  product story (wave to check in), don't pitch breathing detection.
