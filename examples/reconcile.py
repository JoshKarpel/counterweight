from pprint import pprint

from reprisal.components import Div, Text
from reprisal.components.components import (
    build_initial_shadow_tree,
    build_value_tree,
    component,
    reconcile_shadow_tree,
    use_state,
)
from reprisal.styles import Border, BorderKind, Padding, Span, Style

set_state = None


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
    global set_state
    state, set_state = use_state("initial")

    return Text(
        text=f"{text=} {state=}",
        style=Style(
            span=Span(width="auto", height=1),
            border=Border(kind=BorderKind.Light),
            padding=Padding(top=0, bottom=0, left=0, right=0),
        ),
    )


r = root()

# pprint(r.dict())

shadow = build_initial_shadow_tree(r)

# pprint(shadow.dict())

set_state("changed")

# pprint(shadow.dict())

reconciled = reconcile_shadow_tree(shadow)

# pprint(reconciled.dict())

values = build_value_tree(reconciled)

pprint(values.dict())

print("done")
