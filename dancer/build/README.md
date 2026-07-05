# dancer

Generated firmware for **Atech 14-Port Board** (`14port`).

## Modules

- **ESP-NOW Light Link** (`espnow_link`) as `radio` on `port_1`
- **NeoPixel 3x3 Grid** (`neopixel`) as `led` on `port_7`

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
