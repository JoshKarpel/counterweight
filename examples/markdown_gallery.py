"""
A Markdown playground: each feature's source on the left, which you can edit, and how it renders on the right.

Run it with `uv run python -m examples.markdown_gallery`.
Tab and Shift+Tab move between the sections' sources, or click one to edit it,
and the preview beside it follows each edit; Ctrl+R puts back a section's original source.
Escape, or a click outside the sources, stops editing,
and then the arrow keys, PageUp, PageDown, Space, Home and End scroll the gallery, as the wheel always does.
"""

from __future__ import annotations

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import ClearFocus
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.handlers import first, tab_focus
from counterweight.headless import use_scroll_area
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.markdown import markdown_document
from counterweight.styles.utilities import *
from counterweight.widgets import text_area

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


HINT = "tab: edit the next section  ·  ctrl+r: reset it  ·  esc: stop editing, so the keys scroll"


def stop_editing(event: InputEvent, _: Receiver) -> InputResponse:
    """Escape bubbles out of a source, which doesn't edit with it, and clears focus, so the keys reach the gallery."""
    match event:
        case KeyPressed(key=Key.Escape):
            return ClearFocus()
        case _:
            return None


@component
def root() -> Div:
    # Out of Tab's order, as a page's body is, but a click outside the sources focuses the gallery,
    # which stops editing, and with the gallery or nothing focused, key presses reach this element.
    gallery = use_scroll_area(in_focus_order=False)
    return Div(
        style=col | full | gap_height(1) | pad_x(1) | gallery.style,
        handle=gallery.viewport,
        on_input=first(tab_focus, stop_editing, gallery.on_input),
        children=(
            Text(content=HINT, style=text_justify_center | text_wrap_pretty | text_color("slate", 500)),
            *(section(name, source).with_key(name) for name, source in GALLERY),
        ),
    )


@component
def section(name: str, source: str) -> Div:
    """One feature: its source, which this section's state holds as it's edited, beside the source rendered."""
    original = source.removesuffix("\n")
    text, set_text = use_state(original)

    def reset(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.ControlR):
                set_text(original)
                return ()
            case _:
                return None

    return Div(
        style=display_grid
        | grid_template_columns(fr(1), fr(1))
        | gap_width(2)
        | border
        | border_lightrounded
        | border_color("slate", 600)
        | pad_x(1),
        # Ctrl+R bubbles here from the source, which doesn't edit with it, while the source is focused.
        on_input=reset,
        children=(
            Text(content=f" {name} " if text == original else f" {name} (edited) ", style=title),
            # A text area is a scroll container, which adds nothing to the height of a grid row,
            # so it's in a column that's as tall as its rows, which it grows to fill when the preview is taller.
            Div(style=col, children=(text_area(text, set_text, enter_inserts_newline=True, style=grow(1)),)),
            markdown_document(text),
        ),
    )


title = position_absolute | inset_top(-1) | inset_left(1) | clip_to_border | text_color("slate", 400)


if __name__ == "__main__":
    asyncio.run(app(root()))
