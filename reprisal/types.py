from __future__ import annotations

from pydantic import BaseModel, Extra

from reprisal.keys import Key

KeyQueueItem = tuple[Key, ...] | str


class ForbidExtras(BaseModel):
    class Config:
        extra = Extra.forbid


class FrozenForbidExtras(BaseModel):
    class Config:
        frozen = True
        extras = Extra.forbid
