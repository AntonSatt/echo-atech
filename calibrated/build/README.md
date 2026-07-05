# calibrated

Generated firmware for **Atech 14-Port Board** (`14port`).

## Modules

- **Button** (`button`) as `btn` on `port_1`
- **ST7735 TFT Color Display (160x80)** (`st7735_tft`) as `screen` on `port_3, port_4`
- **Rotary Encoder Knob** (`rotary_encoder`) as `knob` on `port_5, port_6`
- **PIR Motion Sensor (AM312)** (`pir`) as `pirm` on `port_7`
- **NeoPixel 3x3 Grid** (`neopixel`) as `led` on `port_9`
- **I2S Speaker (MAX98357A)** (`speaker`) as `spk` on `port_13, port_14`

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
