import asyncio
from collections.abc import Callable
from dataclasses import replace

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Quit
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, KeyPressed, Receiver
from counterweight.handlers import on_click
from counterweight.headless import use_scroll_area
from counterweight.hooks import Setter, use_hovered, use_rects, use_state
from counterweight.keys import Key
from counterweight.markdown import MarkdownStyles, markdown
from counterweight.styles import Style
from counterweight.styles.styles import TextWrap
from counterweight.styles.utilities import *
from counterweight.widgets import TextFieldStyles, text_area

WRAP_MODES: tuple[TextWrap, ...] = ("none", "stable", "pretty", "balance")

WRAPS: dict[TextWrap, Style] = {
    "none": text_wrap_none,
    "stable": text_wrap_stable,
    "pretty": text_wrap_pretty,
    "balance": text_wrap_balance,
}


def wrapped_with(wrap: Style) -> MarkdownStyles:
    """The default Markdown styles, with `wrap` merged over the style of every block of wrapped prose."""
    styles = MarkdownStyles()
    return replace(
        styles,
        paragraph=styles.paragraph | wrap,
        heading_1=styles.heading_1 | wrap,
        heading_2=styles.heading_2 | wrap,
        heading_3=styles.heading_3 | wrap,
        heading_4=styles.heading_4 | wrap,
        heading_5=styles.heading_5 | wrap,
        heading_6=styles.heading_6 | wrap,
        alert_title=styles.alert_title | wrap,
        table_cell_text=styles.table_cell_text | wrap,
    )


# Built once, so `markdown`'s cache sees the same styles on every render.
MARKDOWN_STYLES = {mode: wrapped_with(wrap) for mode, wrap in WRAPS.items()}

SOURCE_STYLES = TextFieldStyles(
    box=border | border_lightrounded | border_color("sky", 600) | pad_x(1) | text_color("sky", 200),
    focused_box=border_color("sky", 400),
    cursor=(text_color("slate", 900) | text_bg("sky", 200)).text_style,
)

SAMPLE = """\
# Wrapping Markdown

A terminal can't hyphenate, so where a paragraph breaks its lines decides how ragged its right edge is.
*Stable* wrapping fills each line as full as it can, **pretty** wrapping avoids leaving one word alone \
on the last line, and **balance** evens out the lengths of every line.

- Each list item wraps beside its bullet, with the same mode as the paragraphs.
- Words in *emphasis*, **strong** text, and `inline code` wrap like the words around them.

> A block quote wraps inside its bar,
> so it has a little less room than the paragraphs around it.

```python
def wrap(text: str, width: int) -> list[str]:
    ...  # Code keeps its lines as written, and scrolls sideways when they're too long to fit.
```
"""


def _make_select(set_wrap_idx: Callable[[int], None], idx: int) -> Callable[[], None]:
    return lambda: set_wrap_idx(idx)


@component
def root() -> Div:
    source, set_source = use_state(SAMPLE)
    wrap_idx, set_wrap_idx = use_state(2)  # start on "pretty"

    def on_input(event: InputEvent, _: Receiver) -> AnyControl | None:
        match event:
            case KeyPressed(key=Key.ControlC):
                return Quit()
            case KeyPressed(key=Key.Tab):
                set_wrap_idx(lambda i: (i + 1) % len(WRAP_MODES))
            case KeyPressed(key=Key.BackTab):
                set_wrap_idx(lambda i: (i - 1) % len(WRAP_MODES))
            case _:
                pass
        return None

    return Div(
        style=col | full,
        on_input=on_input,
        children=(
            toolbar(WRAP_MODES[wrap_idx], set_wrap_idx),
            Div(
                style=row | fill(1) | gap(1) | pad_x(1),
                children=(
                    source_pane(source, set_source),
                    rendered_pane(source, WRAP_MODES[wrap_idx]),
                ),
            ),
            Text(
                content="type to edit Markdown  ·  tab / shift+tab: cycle wrap mode  ·  "
                "wheel, or click and use the keys: scroll  ·  ctrl+c: quit",
                style=text_justify_center | text_color("slate", 500) | pad_y(1),
            ),
        ),
    )


@component
def toolbar(
    mode: TextWrap,
    set_wrap_idx: Callable[[int | Callable[[int], int]], None],
) -> Div:
    return Div(
        style=row | pad_x(1) | pad_y(1),
        children=(
            Text(
                content="Markdown Text Wrap Demo",
                style=fill(1) | text_color("amber", 400),
            ),
            Div(
                style=row | justify_children_space_evenly,
                children=tuple(
                    mode_button(
                        label=m,
                        active=(m == mode),
                        select=_make_select(set_wrap_idx, i),
                    )
                    for i, m in enumerate(WRAP_MODES)
                ),
            ),
        ),
    )


@component
def source_pane(source: str, set_source: Setter[str]) -> Div:
    return Div(
        style=fill(1) | col,
        children=(
            # fill(1) makes the text area as tall as the pane rather than as tall as its rows.
            text_area(
                source,
                set_source,
                style=fill(1),
                styles=SOURCE_STYLES,
                enter_inserts_newline=True,
                auto_focus=True,
            ),
            Text(
                content=" source ",
                style=position_absolute | inset_top(0) | inset_right(2) | z(1) | text_color("sky", 600),
            ),
        ),
    )


@component
def rendered_pane(source: str, mode: TextWrap) -> Div:
    rects = use_rects()
    w = rects.content.width
    # Both ways, for the lines that "none" leaves as wide as they're written. A click focuses it, for the keys.
    area = use_scroll_area(axis="both")

    return Div(
        style=fill(1)
        | col
        | border
        | border_lightrounded
        | border_color("violet", 400 if area.focus.is_focused else 600)
        | pad_x(1),
        on_input=area.on_input,
        children=(
            Text(
                content=f" {w}c " if w > 0 else "",
                style=position_absolute | inset_top(-1) | inset_right(1) | clip_to_border | text_color("violet", 600),
            ),
            # Inside the border, so the width label above stays put while the document scrolls.
            Div(
                style=fill(1) | col | text_color("violet", 200) | area.style,
                handle=area.viewport,
                children=(markdown(source, MARKDOWN_STYLES[mode]),),
            ),
        ),
    )


@component
def mode_button(label: str, active: bool, select: Callable[[], None]) -> Text:
    hovered = use_hovered()

    if active:
        style = border | border_heavy | border_color("violet", 400) | text_color("violet", 100)
    elif hovered.border:
        style = border | border_color("slate", 400) | text_color("slate", 200)
    else:
        style = border | border_color("slate", 700) | text_color("slate", 500)

    return Text(
        content=f" {label} ",
        on_input=on_click(select),
        style=style,
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
