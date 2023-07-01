from pprint import pprint

from reprisal.components import Div, Text
from reprisal.components.components import (
    build_concrete_element_tree,
    component,
    render_shadow_node_from_previous,
    use_state,
)

setters = {}


@component
def root() -> Div:
    return Div(
        children=(
            child("first"),
            child("second"),
        ),
    )


@component
def child(text: str) -> Text:
    a, set_a = use_state("a")
    b, set_b = use_state("b")

    setters[text, "a"] = set_a
    setters[text, "b"] = set_b

    return Text(
        text=f"{text=} {a=} {b=}",
    )


print("-" * 40)

r = render_shadow_node_from_previous(root(), None)
pprint(r.dict(exclude_defaults=True))
print("-" * 40)

e = build_concrete_element_tree(r)
pprint(e.dict(exclude_defaults=True))
print("-" * 40)

setters["first", "a"]("c")

r2 = render_shadow_node_from_previous(root(), r)
pprint(r2.dict(exclude_defaults=True))
print("-" * 40)

e2 = build_concrete_element_tree(r2)
pprint(e2.dict(exclude_defaults=True))
print("-" * 40)
