# conductor

Generated firmware for **Atech 14-Port Board** (`14port`).

## Modules

- **ESP-NOW Light Link** (`espnow_link`) as `radio` on `port_2`
- **ST7735 TFT Color Display (160x80)** (`st7735_tft`) as `screen` on `port_3, port_4`
- **Rotary Encoder Knob** (`rotary_encoder`) as `knob` on `port_5, port_6`
- **NeoPixel 3x3 Grid** (`neopixel`) as `led` on `port_9`

## Build & flash

```bash
pio run                         # build
pio run -t upload               # flash
```

Or from Python via the Atech SDK:

```python
from atech import Project
Project.load('project.yaml').upload()
```
