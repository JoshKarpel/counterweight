"""
A gallery of the Markdown that `markdown` renders: each feature's source on the left, and how it renders on the right.

Run it with `uv run python -m examples.markdown_gallery`.
The gallery is longer than most screens, so it's cut off at the bottom edge.
"""

from __future__ import annotations

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.highlighting import code_block
from counterweight.markdown import markdown
from counterweight.styles.utilities import *

GALLERY = (
    (
        "Inline spans",
        """\
*Emphasis*, **strong**, ***both***,
~~strikethrough~~ and ~with one tilde~,
`inline code`, [a link](https://commonmark.org),
and ![an image](https://example.com/cat.png).
A backslash at the end of a line\\
is a hard break.
""",
    ),
    (
        "Bare URLs",
        """\
Bare URLs like https://commonmark.org
and www.example.com are links,
as are emails like someone@example.com
and <https://commonmark.org> in angle brackets.
""",
    ),
    (
        "Headings",
        """\
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6
""",
    ),
    (
        "Lists",
        """\
- Himalayas
  - Everest
  - Kangchenjunga
- Karakoram

9. Ninth
10. Tenth

- A loose list

- has gaps between items
""",
    ),
    (
        "Task lists",
        """\
- [x] Pack the tent
- [ ] Check the weather
- A plain item

1. [x] Base camp
2. [ ] Summit
""",
    ),
    (
        "Block quotes",
        """\
> Because it's there.
>
> > Nested, too.
""",
    ),
    (
        "Alerts",
        """\
> [!NOTE]
> Worth knowing.

> [!TIP]
> Helpful advice.

> [!IMPORTANT]
> Crucial information.

> [!WARNING]
> Needs attention.

> [!CAUTION]
> Risky consequences.
""",
    ),
    (
        "Code",
        """\
```python
def tallest(peaks):
    return max(peaks, key=lambda p: p.height)
```

    Indented code isn't highlighted.
""",
    ),
    (
        "Tables",
        """\
| Peak    | Range     | Height (m) |
|:--------|:---------:|-----------:|
| Everest | Himalayas |       8849 |
| K2      | Karakoram |       8611 |
""",
    ),
    (
        "Footnotes",
        """\
Everest was first climbed in 1953[^first],
and K2 a year later[^k2].

[^first]: By Tenzing Norgay and Edmund Hillary.
[^k2]: By Lino Lacedelli and Achille Compagnoni.
""",
    ),
    (
        "Front matter",
        """\
---
title: Peaks
tags: [mountains, asia]
---

YAML front matter, at the very top of a document.
""",
    ),
    (
        "Math",
        """\
Math like $e^{i\\pi} + 1 = 0$ is shown as written,
but prices like $5 and $10 are text.

$$
\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}
$$
""",
    ),
    (
        "Thematic breaks and HTML",
        """\
Above the break.

---

<details>
Raw HTML is shown as written.
</details>
""",
    ),
)


@component
def root() -> Div:
    return Div(
        style=col | gap_height(1) | pad_x(1),
        children=tuple(section(name, source) for name, source in GALLERY),
    )


def section(name: str, source: str) -> Div:
    return Div(
        style=display_grid
        | grid_template_columns(fr(1), fr(1))
        | gap_width(2)
        | border
        | border_lightrounded
        | border_color("slate", 600)
        | pad_x(1),
        children=(
            Text(content=f" {name} ", style=title),
            code_block(source.removesuffix("\n"), "markdown", style=pad_x(1)),
            markdown(source),
        ),
    )


title = position_absolute | inset_top(-1) | inset_left(1) | text_color("slate", 400)


if __name__ == "__main__":
    asyncio.run(app(root()))
