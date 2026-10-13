import asyncio

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

SCREENSHOTS = [ScreenshotSpec(root(), "markdown-document", (60, 25))]


if __name__ == "__main__":
    asyncio.run(app(root()))
