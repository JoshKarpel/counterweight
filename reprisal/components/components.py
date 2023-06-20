from __future__ import annotations

from collections.abc import Callable

from pydantic import Field

from reprisal.events import KeyPressed
from reprisal.styles import Style
from reprisal.types import FrozenForbidExtras


class Div(FrozenForbidExtras):
    children: tuple[AnyElement, ...] = Field(
        default=...,
        exclude=True,
    )
    style: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], None] | None = None


class Text(FrozenForbidExtras):
    text: str
    style: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], None] | None = None


AnyElement = Div | Text

Div.update_forward_refs()
