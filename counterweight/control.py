from __future__ import annotations

from enum import Enum


class Control(Enum):
    Quit = "quit"
    Bell = "bell"
    Screenshot = "screenshot"
    ToggleBorderHealing = "toggle-border-healing"
