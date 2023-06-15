from __future__ import annotations

from pydantic import Field

from reprisal.styles import Style
from reprisal.types import FrozenForbidExtras


class Div(FrozenForbidExtras):
    children: tuple[AnyElement, ...] = Field(
        default=...,
        exclude=True,
    )
    style: Style = Field(default=Style())


class Text(FrozenForbidExtras):
    text: str
    style: Style = Field(default=Style())


AnyElement = Div | Text

Div.update_forward_refs()
