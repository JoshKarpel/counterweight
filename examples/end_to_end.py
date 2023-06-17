import sys
import termios
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from functools import partial
from io import UnsupportedOperation
from typing import Any, TextIO

from reprisal.compositor import BoxDimensions, Edge, Rect, build_layout_tree, debug, paint
from reprisal.elements.elements import Div, Text
from reprisal.render import Root, use_state
from reprisal.styles.styles import Border, BorderKind, Padding, Span, Style
from reprisal.vtparser import (
    CSI_LOOKUP,
    ESC_LOOKUP,
    EXECUTE_LOOKUP,
    UNESCAPED,
    Action,
    Keys,
    VTParser,
)


@Root
def time():
    now, set_now = use_state(datetime.now())

    return Div(
        children=(
            Text(
                text=f"{now}",
                style=Style(
                    span=Span(width="auto", height=1),
                    border=Border(kind=BorderKind.Light),
                    padding=Padding(top=0, bottom=0, left=0, right=0),
                ),
            ),
        ),
        style=Style(
            border=Border(kind=BorderKind.Heavy),
        ),
        on_key=lambda _: set_now(datetime.now()),
    )


b = BoxDimensions(
    content=Rect(x=0, y=0, width=30, height=0),
    margin=Edge(),
    border=Edge(),
    padding=Edge(),
)


def handler(action, intermediate_chars, params, char, r):
    print(f"{intermediate_chars=} {params=} {action=} {char=} {chr(char)=} {hex(char)=}")
    match action, intermediate_chars, params, char:
        case Action.CSI_DISPATCH, (), params, char:
            keys = CSI_LOOKUP[(params, char)]
        case Action.ESC_DISPATCH, intermediate_chars, (), char:
            keys = ESC_LOOKUP[(intermediate_chars, char)]
        case Action.PRINT, (), (), char:
            keys = UNESCAPED.get(char, chr(char))
        case Action.EXECUTE, (), (), char:
            keys = EXECUTE_LOOKUP[char]
        case _, _, _, _:
            print("did nothing")
            keys = None
    print(keys)
    if keys == (Keys.Space,):
        print("hi!")
        if r.on_key:
            r.on_key(keys)
        r = time.render()
        t = build_layout_tree(r)
        t.layout(b)
        p = paint(t)
        print(debug(p, t.dims.margin_rect()))


LFLAG = 3
CC = 6

try:
    ORIGINAL_TCGETATTR: list[Any] | None = termios.tcgetattr(sys.stdin)
except (UnsupportedOperation, termios.error):
    ORIGINAL_TCGETATTR = None


def start_no_echo(stream: TextIO) -> None:
    if ORIGINAL_TCGETATTR is None:
        return

    mode = deepcopy(ORIGINAL_TCGETATTR)

    mode[LFLAG] = mode[LFLAG] & ~(termios.ECHO | termios.ICANON)
    mode[CC][termios.VMIN] = 1
    mode[CC][termios.VTIME] = 0

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, mode)


def reset_tty(stream: TextIO) -> None:
    if ORIGINAL_TCGETATTR is None:
        return

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, ORIGINAL_TCGETATTR)


@contextmanager
def no_echo() -> Iterator[None]:
    try:
        start_no_echo(sys.stdin)

        yield
    finally:
        reset_tty(sys.stdin)


print("starting...")

r = time.render()
t = build_layout_tree(r)
t.layout(b)
p = paint(t)
print(debug(p, t.dims.margin_rect()))

parser = VTParser()

with no_echo():
    while True:
        char = sys.stdin.read(1)
        print(f"read {char=} {ord(char)=} {hex(ord(char))=}")
        parser.advance(ord(char), partial(handler, r=r))
