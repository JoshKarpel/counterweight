"""
Hooks: use_focus

An order form whose fields take focus in turn, with a confirmation dialog that keeps focus inside it.
"""

import asyncio
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import ClearFocus
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import each
from counterweight.handlers import first
from counterweight.handlers import focus_on_press
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.hooks import Focus
from counterweight.hooks import FocusHandle
from counterweight.hooks import Setter
from counterweight.hooks import toggle
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import *

# --8<-- [start:example]

SIZES = ("Small", "Medium", "Large")
PAPERS = ("Stripes", "Dots", "Plain")
TIPS = ("Enter moves to the next field", "Press a label to focus its field", "Tab stays inside the dialog")


def marked(focus: Focus, content: str) -> str:
    return f"{'▸' if focus.is_focused else ' '} {content}"


def field_style(focus: Focus, is_focusable: bool = True) -> Style:
    if not is_focusable:
        return text_color("slate", 600)
    return text_bg("indigo", 700) | text_color("slate", 50) if focus.is_focused else text_color("slate", 300)


@component
def choice_field(
    options: tuple[str, ...], handle: FocusHandle, auto_focus: bool = False, is_focusable: bool = True
) -> Text:
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable)
    index, set_index = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Left):
                set_index(lambda i: (i - 1) % len(options))
                return ()
            case KeyPressed(key=Key.Right):
                set_index(lambda i: (i + 1) % len(options))
                return ()
            case _:
                return None

    return Text(
        content=marked(focus, f"< {options[index]} >"),
        style=field_style(focus, is_focusable),
        on_input=first(on_input, focus_receiver_on_press),
    )


@component
def quantity_field(handle: FocusHandle) -> Text:
    focus = use_focus(handle=handle)
    quantity, set_quantity = use_state(1)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Up):
                set_quantity(lambda q: q + 1)
                return ()
            case KeyPressed(key=Key.Down):
                set_quantity(lambda q: max(q - 1, 1))
                return ()
            case _:
                return None

    return Text(
        content=marked(focus, f"{quantity} ▴▾"),
        style=field_style(focus),
        on_input=first(on_input, focus_receiver_on_press),
    )


@component
def toggle_field(is_on: bool, set_on: Setter[bool], handle: FocusHandle) -> Text:
    focus = use_focus(handle=handle)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                set_on(toggle)
                return ()
            case _:
                return None

    return Text(
        content=marked(focus, "[x]" if is_on else "[ ]"),
        style=field_style(focus),
        on_input=first(on_input, focus_receiver_on_press),
    )


@component
def help_panel() -> Div:
    # A press focuses it, but Enter and Tab never stop on it.
    focus = use_focus(in_focus_order=False)
    page, set_page = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Left):
                set_page(lambda p: (p - 1) % len(TIPS))
                return ()
            case KeyPressed(key=Key.Right):
                set_page(lambda p: (p + 1) % len(TIPS))
                return ()
            case _:
                return None

    return Div(
        style=border
        | border_lightrounded
        | pad_x(1)
        | (border_color("indigo", 400) if focus.is_focused else border_color("slate", 600)),
        on_input=first(on_input, focus_receiver_on_press),
        children=(
            Text(
                style=position_absolute | inset_left(1) | inset_top(-1) | clip_to_border,
                content=f" {marked(focus, f'Tip {page + 1}/{len(TIPS)}')} ",
            ),
            Text(content=TIPS[page], style=text_color("slate", 400)),
        ),
    )


@component
def button(
    label: str, action: Callable[[], InputResponse], auto_focus: bool = False, handle: FocusHandle | None = None
) -> Text:
    focus = use_focus(auto_focus=auto_focus, handle=handle)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                return action()
            case _:
                return None

    return Text(
        content=marked(focus, label),
        style=pad_x(1) | border | border_lightrounded | field_style(focus),
        on_input=first(on_input, each(on_click(action), focus_receiver_on_press)),
    )


dialog_box = position_absolute | inset(0) | margin_auto | fit_content_width | fit_content_height


@component
def confirmation(close: Callable[[], None], return_to: FocusHandle) -> Div:
    def close_and_return() -> InputResponse:
        close()
        return FocusOn(return_to)

    return Div(
        style=dialog_box | col | align_children_center | border | border_double | pad_x(2),
        # Tab from either button reaches this element before the form's, and cycles between the two.
        on_input=tab_focus,
        children=(
            Text(content="Place this order?"),
            Div(
                style=row | gap(1),
                children=(
                    button("Confirm", close_and_return),
                    button("Cancel", close_and_return, auto_focus=True),
                ),
            ),
        ),
    )


@component
def labelled(label: str, handle: FocusHandle, field: Component) -> Div:
    return Div(
        style=row | gap(1),
        children=(Text(content=f"{label:<10}", on_input=focus_on_press(handle)), field),
    )


@component
def order_form() -> Div:
    size, _ = use_state(FocusHandle)
    quantity, _ = use_state(FocusHandle)
    gift_wrap, _ = use_state(FocusHandle)
    paper, _ = use_state(FocusHandle)
    submit, _ = use_state(FocusHandle)
    is_wrapped, set_wrapped = use_state(False)
    is_confirming, set_confirming = use_state(False)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                return FocusNext(within=receiver.subtree)
            case _:
                return None

    def open_confirmation() -> InputResponse:
        set_confirming(True)
        # With nothing focused, the dialog's Cancel button takes focus as it mounts.
        return ClearFocus()

    return Div(
        style=col | gap(1) | border | border_lightrounded | pad_x(1),
        on_input=first(on_input, tab_focus),
        children=(
            Div(
                style=col,
                children=(
                    labelled("Size", size, choice_field(SIZES, size, auto_focus=True)),
                    labelled("Quantity", quantity, quantity_field(quantity)),
                    labelled("Gift wrap", gift_wrap, toggle_field(is_wrapped, set_wrapped, gift_wrap)),
                    labelled("Paper", paper, choice_field(PAPERS, paper, is_focusable=is_wrapped)),
                ),
            ),
            help_panel(),
            Div(style=row, children=(button("Submit", open_confirmation, handle=submit),)),
            *([confirmation(close=lambda: set_confirming(False), return_to=submit)] if is_confirming else []),
        ),
    )


# --8<-- [end:example]


ROOTS = (order_form,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position


def press(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


ENTER = KeyPressed(key=Key.Enter)
TAB = KeyPressed(key=Key.Tab)
GIFT_WRAP_LABEL = (3, 3)
HELP_PANEL = (5, 7)

ON_GIFT_WRAP = (ENTER, *press(*GIFT_WRAP_LABEL))
ON_SUBMIT = (*ON_GIFT_WRAP, ENTER)
MODAL_OPEN = (*ON_SUBMIT, ENTER)
MODAL_TABBED = (*MODAL_OPEN, TAB, TAB)
MODAL_CLOSED = (*MODAL_TABBED, ENTER)

STILLS = [
    Still("focus-form-startup", order_form(), (40, 14)),
    Still("focus-form-enter", order_form(), (40, 14), steps=(ENTER,)),
    Still("focus-form-label", order_form(), (40, 14), steps=ON_GIFT_WRAP),
    Still("focus-form-submit", order_form(), (40, 14), steps=ON_SUBMIT),
    Still("focus-form-modal", order_form(), (40, 14), steps=MODAL_OPEN),
    Still("focus-form-modal-tab", order_form(), (40, 14), steps=MODAL_TABBED),
    Still("focus-form-modal-closed", order_form(), (40, 14), steps=MODAL_CLOSED),
    Still("focus-form-help", order_form(), (40, 14), steps=(*press(*HELP_PANEL), KeyPressed(key=Key.Right))),
]


DEMOS = [
    Demo(
        "focus-form",
        order_form(),
        (40, 14),
        steps=paced(
            [
                ENTER,
                *press(*GIFT_WRAP_LABEL),
                ENTER,
                ENTER,
                TAB,
                TAB,
                ENTER,
                *press(*HELP_PANEL),
                KeyPressed(key=Key.Right),
            ],
            every=timedelta(milliseconds=800),
        ),
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(order_form()))
