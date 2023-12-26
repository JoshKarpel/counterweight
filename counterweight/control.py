from __future__ import annotations

from typing import Union

from counterweight.types import FrozenForbidExtras


class _Control(FrozenForbidExtras):
    pass


class Quit(_Control):
    pass


class Bell(_Control):
    pass


class Screenshot(_Control):
    pass


class ToggleBorderHealing(_Control):
    pass


AnyControl = Union[Quit, Bell, Screenshot, ToggleBorderHealing]
