from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:title]


def title(content: str) -> Text:
    return Text(content=f" {content} ", style=position_absolute | inset_top(-1) | inset_left(1))


# --8<-- [end:title]

# --8<-- [start:justify]


@component
def justify() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | justify | border_light,
                children=[
                    title(name),
                    Text(style=border_heavy, content="a"),
                    Text(style=border_heavy, content="bb"),
                    Text(style=border_heavy, content="ccc"),
                ],
            )
            for name, justify in (
                ("justify_children_start", justify_children_start),
                ("justify_children_center", justify_children_center),
                ("justify_children_end", justify_children_end),
                ("justify_children_space_between", justify_children_space_between),
                ("justify_children_space_around", justify_children_space_around),
                ("justify_children_space_evenly", justify_children_space_evenly),
            )
        ],
    )


# --8<-- [end:justify]

# --8<-- [start:align]


@component
def align() -> Div:
    return Div(
        style=row | full,
        children=[
            Div(
                style=row | align | grow(1) | min_width(0) | border_light,
                children=[
                    title(name),
                    Text(style=border_heavy, content="a"),
                    Text(style=border_heavy, content="b\nb"),
                    Text(style=border_heavy, content="c\nc\nc"),
                ],
            )
            for name, align in (
                ("align_children_start", align_children_start),
                ("align_children_center", align_children_center),
                ("align_children_end", align_children_end),
                ("align_children_stretch", align_children_stretch),
            )
        ],
    )


# --8<-- [end:align]

# --8<-- [start:align-self]


@component
def align_self() -> Div:
    return Div(
        style=row | align_children_start | gap(1) | full | border_light,
        children=[
            title("row | align_children_start"),
            Text(style=border_heavy, content="no align_self"),
            Text(style=align_self_center | border_heavy, content="align_self_center"),
            Text(style=align_self_end | border_heavy, content="align_self_end"),
            Text(style=align_self_stretch | border_heavy, content="align_self_stretch"),
        ],
    )


# --8<-- [end:align-self]

# --8<-- [start:center]


@component
def center() -> Div:
    return Div(
        style=row | full,
        children=[
            Div(
                style=row | align_children_center | justify_children_center | grow(1) | border_light,
                children=[title("flexbox"), Text(style=border_heavy, content="centered")],
            ),
            Div(
                style=display_grid | align_children_center | justify_items_center | grow(1) | border_light,
                children=[title("grid"), Text(style=border_heavy, content="centered")],
            ),
        ],
    )


# --8<-- [end:center]

TALL = "\n".join(f"line {n}" for n in range(1, 13))

# --8<-- [start:overflow]


@component
def overflow() -> Div:
    return Div(
        style=row | pad_y(4),
        children=[
            Div(
                style=col | justify | grow(1) | border_light,
                children=[title(name), Text(content=TALL)],
            )
            for name, justify in (
                ("justify_children_center", justify_children_center),
                ("justify_children_center_unsafe", justify_children_center_unsafe),
            )
        ],
    )


# --8<-- [end:overflow]

SCREENSHOTS = [
    ScreenshotSpec(justify, "layout-justify-children", (50, 30)),
    ScreenshotSpec(align, "layout-align-children", (120, 9)),
    ScreenshotSpec(align_self, "layout-align-self", (80, 9)),
    ScreenshotSpec(center, "layout-center", (50, 9)),
    ScreenshotSpec(overflow, "layout-center-overflow", (70, 17)),
]
