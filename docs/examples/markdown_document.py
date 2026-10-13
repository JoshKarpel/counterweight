import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.markdown import markdown
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

README = """\
# Peaks

The *fourteen* peaks above **8000 m** are all in Asia;
see [the list](https://en.wikipedia.org/wiki/Eight-thousander).

> Because it's there.

- Himalayas
  - Everest
  - Kangchenjunga
- Karakoram
  - K2

| Peak | Height (m) |
|:-----|-----------:|
| Everest | 8849 |
| K2 | 8611 |

```python
tallest = max(peaks, key=lambda p: p.height)
```
"""


@component
def root() -> Div:
    return Div(style=col | pad_x(1), children=[markdown(README)])


# --8<-- [end:example]

# --8<-- [start:github]

EXPEDITION = """\
---
peak: K2
---

- [x] Reach base camp
- [ ] Summit, weather permitting[^window]

> [!WARNING]
> Bottlenecks form above camp four.

Forecasts are at www.mountain-forecast.com.

[^window]: Usually in late July.
"""


@component
def github() -> Div:
    return Div(style=col | pad_x(1), children=[markdown(EXPEDITION)])


# --8<-- [end:github]

SCREENSHOTS = [
    ScreenshotSpec(root(), "markdown-document", (60, 25)),
    ScreenshotSpec(github(), "markdown-github", (60, 12)),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (root, github)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else root()))
