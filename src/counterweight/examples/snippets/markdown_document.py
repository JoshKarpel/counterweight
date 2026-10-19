"""
Rich text: Markdown

A Markdown document rendered, with GitHub's extensions, scrolling, and blocks wider than the view.
"""

import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.handlers import first
from counterweight.handlers import scroll_on_keys
from counterweight.handlers import scroll_on_wheel
from counterweight.hooks import use_focus
from counterweight.markdown import markdown_document
from counterweight.styles.utilities import *

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


ROOTS = (root, github, scrolling, wide)

# --8<-- [start:scenes]

from counterweight.events import KeyPressed
from counterweight.events import MouseScrolledRight
from counterweight.examples.scenes import Still
from counterweight.geometry import Position
from counterweight.keys import Key

WHEEL_RIGHT = MouseScrolledRight(absolute=Position(5, 2))

STILLS = [
    Still("markdown-document", root(), (60, 25)),
    Still("markdown-github", github(), (60, 12)),
    Still("markdown-scrolling", scrolling(), (60, 12)),
    Still("markdown-scrolling-paged", scrolling(), (60, 12), steps=[KeyPressed(key=Key.PageDown)]),
    Still("markdown-wide", wide(), (40, 3)),
    Still("markdown-wide-scrolled", wide(), (40, 3), steps=[WHEEL_RIGHT] * 4),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
