from __future__ import annotations

from pydantic import BaseModel, Extra


class ForbidExtras(BaseModel):
    class Config:
        extra = Extra.forbid


class FrozenForbidExtras(ForbidExtras):
    class Config:
        frozen = True
