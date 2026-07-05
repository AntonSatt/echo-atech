# smoke_test

Generated firmware for **Atech 14-Port Board** (`14port`).

## Modules


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
