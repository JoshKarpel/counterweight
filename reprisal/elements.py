from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Extra, Field


class FrozenForbidExtras(BaseModel):
    class Config:
        frozen = True
        extras = Extra.forbid


class Cells(FrozenForbidExtras):
    cells: int = 0


AnyDistance = Cells


class BoxDimensions(FrozenForbidExtras):
    top: AnyDistance
    bottom: AnyDistance
    left: AnyDistance
    right: AnyDistance

    @classmethod
    def zero(cls) -> BoxDimensions:
        return BoxDimensions(
            top=Cells(cells=0),
            bottom=Cells(cells=0),
            left=Cells(cells=0),
            right=Cells(cells=0),
        )


class BorderKind(Enum):
    Blank = "      "
    Light = "│─┌┐└┘"
    Heavy = "┃━┏┓┗┛"


class Border(FrozenForbidExtras):
    kind: BorderKind = Field(default=BorderKind.Blank)
    dimensions: BoxDimensions = Field(default=BoxDimensions.zero())


class Style(FrozenForbidExtras):
    margin: BoxDimensions = Field(default=BoxDimensions.zero())
    border: Border = Field(default=Border())
    padding: BoxDimensions = Field(default=BoxDimensions.zero())


class Div(FrozenForbidExtras):
    children: tuple[AnyElement, ...]
    style: Style = Field(default=Style())


class Text(FrozenForbidExtras):
    text: str
    style: Style = Field(default=Style())


AnyElement = Div | Text

Div.update_forward_refs()
