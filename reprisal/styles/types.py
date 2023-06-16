from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

S = TypeVar("S", bound=BaseModel)
