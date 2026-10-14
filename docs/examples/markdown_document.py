import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.events import KeyPressed
from counterweight.events import MouseScrolledRight
from counterweight.geometry import Position
from counterweight.handlers import first
from counterweight.handlers import scroll_on_keys
from counterweight.handlers import scroll_on_wheel
from counterweight.hooks import use_focus
from counterweight.keys import Key
from counterweight.markdown import markdown_document
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
    return Div(style=col | pad_x(1), children=(markdown_document(README),))


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
    return Div(style=col | pad_x(1), children=(markdown_document(EXPEDITION),))


# --8<-- [end:github]

# --8<-- [start:scrolling]


@component
def scrolling() -> Div:
    # Focused, so the keys reach scroll_on_keys.
    use_focus(auto_focus=True)
    return Div(
        style=col | full | border | border_lightrounded | pad_x(1) | overflow_y_scroll,
        on_input=first(scroll_on_keys(), scroll_on_wheel()),
        children=(markdown_document(README),),
    )


# --8<-- [end:scrolling]

# --8<-- [start:wide]

INSTALL = """\
Install it with:

```bash
uv add counterweight markdown-it-py mdit-py-plugins pygments
```
"""


@component
def wide() -> Div:
    return Div(style=col | pad_x(1), children=(markdown_document(INSTALL),))


# --8<-- [end:wide]

WHEEL_RIGHT = MouseScrolledRight(absolute=Position(5, 2))

SCREENSHOTS = [
    ScreenshotSpec(root(), "markdown-document", (60, 25)),
    ScreenshotSpec(github(), "markdown-github", (60, 12)),
    ScreenshotSpec(scrolling(), "markdown-scrolling", (60, 12)),
    ScreenshotSpec(scrolling(), "markdown-scrolling-paged", (60, 12), events=[KeyPressed(key=Key.PageDown)]),
    ScreenshotSpec(wide(), "markdown-wide", (40, 3)),
    ScreenshotSpec(wide(), "markdown-wide-scrolled", (40, 3), events=[WHEEL_RIGHT] * 4),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (root, github, scrolling, wide)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else root()))
