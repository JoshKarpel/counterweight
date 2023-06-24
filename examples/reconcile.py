from pprint import pprint

from reprisal.components import Div, Text
from reprisal.components.components import build_shadow_tree, build_value_tree, component
from reprisal.styles import Border, BorderKind, Padding, Span, Style


@component
def root():
    return Div(
        children=(
            child("first"),
            child("second"),
        ),
        style=Style(
            border=Border(kind=BorderKind.Heavy),
        ),
    )


@component
def child(text: str):
    return Text(
        text=text,
        style=Style(
            span=Span(width="auto", height=1),
            border=Border(kind=BorderKind.Light),
            padding=Padding(top=0, bottom=0, left=0, right=0),
        ),
    )


r = root()

# pprint(r.dict())

shadow = build_shadow_tree(r)

pprint(shadow.dict())

values = build_value_tree(shadow)

pprint(values.dict())
