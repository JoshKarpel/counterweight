from __future__ import annotations

from collections.abc import Callable

from pydantic import Field

from reprisal.styles import Style
from reprisal.types import FrozenForbidExtras, KeyQueueItem


class Div(FrozenForbidExtras):
    children: tuple[AnyElement, ...] = Field(
        default=...,
        exclude=True,
    )
    style: Style = Field(default=Style())
    on_key: Callable[[KeyQueueItem], None] | None = None


class Text(FrozenForbidExtras):
    text: str
    style: Style = Field(default=Style())
    on_key: Callable[[KeyQueueItem], None] | None = None


AnyElement = Div | Text

Div.update_forward_refs()
