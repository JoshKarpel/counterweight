from __future__ import annotations

from pydantic import BaseModel, Extra

from reprisal.input import Keys

KeyQueueItem = tuple[Keys, ...] | str


class ForbidExtras(BaseModel):
    class Config:
        extra = Extra.forbid


class FrozenForbidExtras(BaseModel):
    class Config:
        frozen = True
        extras = Extra.forbid
