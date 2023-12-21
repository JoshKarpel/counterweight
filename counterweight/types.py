from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class ForbidExtras(BaseModel):
    model_config: ClassVar[ConfigDict] = {
        "extra": "forbid",
    }


class FrozenForbidExtras(ForbidExtras):
    model_config: ClassVar[ConfigDict] = {
        "frozen": True,
    }
