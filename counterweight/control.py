from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Union
from xml.etree.ElementTree import Element, tostring


@dataclass(frozen=True)
class Quit:
    pass


@dataclass(frozen=True)
class Bell:
    pass


@dataclass(frozen=True)
class Screenshot:
    handler: Callable[[Element], None]

    @classmethod
    def to_file(cls, path: Path) -> Screenshot:
        def handler(element: Element) -> None:
            with path.open("w") as f:
                f.write(tostring(element, encoding="unicode"))

        return cls(handler=handler)


@dataclass(frozen=True)
class ToggleBorderHealing:
    pass


AnyControl = Union[Quit, Bell, Screenshot, ToggleBorderHealing]
