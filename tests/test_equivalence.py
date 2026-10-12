from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

import pytest

from counterweight.elements import Div, Text
from counterweight.equivalence import equivalent
from counterweight.events import KeyPressed


def handler_capturing(value: object) -> Callable[[], object]:
    def handler() -> object:
        return value

    return handler


def key_handler_capturing(value: object) -> Callable[[KeyPressed], None]:
    def on_key(_: KeyPressed) -> None:
        print(value)

    return on_key


def handler_with_default(value: object) -> Callable[[], object]:
    def handler(captured: object = value) -> object:
        return captured

    return handler


def handler_with_keyword_default(value: object) -> Callable[[], object]:
    def handler(*, captured: object = value) -> object:
        return captured

    return handler


def recursive_handler(value: object) -> Callable[[int], object]:
    def handler(depth: int) -> object:
        return value if depth == 0 else handler(depth - 1)

    return handler


def unbound_capture(bind: bool) -> Callable[[], object]:
    """A closure over a variable that `bind=False` leaves unbound, so its cell is empty."""

    def handler() -> object:
        return later

    if bind:
        later = "bound"
    return handler


def other_handler() -> None:
    return None


def target(first: object, second: object) -> None:
    return None


@dataclass(frozen=True, slots=True)
class Holder:
    value: object

    def handle(self) -> object:
        return self.value

    def other(self) -> object:
        return self.value


@pytest.mark.parametrize(
    ("a", "b"),
    [
        pytest.param(handler_capturing("x"), handler_capturing("x"), id="closures-capturing-equal-values"),
        pytest.param(handler_capturing(["x"]), handler_capturing(["x"]), id="closures-capturing-equal-lists"),
        pytest.param(handler_with_default("x"), handler_with_default("x"), id="equal-defaults"),
        pytest.param(handler_with_keyword_default("x"), handler_with_keyword_default("x"), id="equal-keyword-defaults"),
        pytest.param(recursive_handler("x"), recursive_handler("x"), id="closures-referring-to-themselves"),
        pytest.param(unbound_capture(bind=False), unbound_capture(bind=False), id="closures-with-unbound-cells"),
        pytest.param(
            handler_capturing(handler_capturing("x")),
            handler_capturing(handler_capturing("x")),
            id="closures-capturing-equivalent-closures",
        ),
        pytest.param(partial(target, "x", second="y"), partial(target, "x", second="y"), id="partials"),
        pytest.param(Holder("x").handle, Holder("x").handle, id="methods-bound-to-equal-objects"),
        pytest.param(
            Div(children=[Text(content="x", on_key=key_handler_capturing("x"))]),
            Div(children=[Text(content="x", on_key=key_handler_capturing("x"))]),
            id="elements-holding-equivalent-handlers",
        ),
        pytest.param({"k": handler_capturing("x")}, {"k": handler_capturing("x")}, id="dicts"),
        pytest.param(1, 1.0, id="different-types-compared-with-eq"),
    ],
)
def test_equivalent(a: object, b: object) -> None:
    assert equivalent(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        pytest.param(handler_capturing("x"), handler_capturing("y"), id="closures-capturing-different-values"),
        pytest.param(handler_with_default("x"), handler_with_default("y"), id="different-defaults"),
        pytest.param(
            handler_with_keyword_default("x"), handler_with_keyword_default("y"), id="different-keyword-defaults"
        ),
        pytest.param(recursive_handler("x"), recursive_handler("y"), id="self-referring-closures-capturing-different"),
        pytest.param(handler_capturing("x"), other_handler, id="different-code"),
        pytest.param(unbound_capture(bind=False), unbound_capture(bind=True), id="unbound-and-bound-cells"),
        pytest.param(
            handler_capturing(handler_capturing("x")),
            handler_capturing(handler_capturing("y")),
            id="closures-capturing-different-closures",
        ),
        pytest.param(partial(target, "x", second="y"), partial(target, "x", second="z"), id="partials"),
        pytest.param(Holder("x").handle, Holder("y").handle, id="methods-bound-to-different-objects"),
        pytest.param(Holder("x").handle, Holder("x").other, id="different-methods"),
        pytest.param(
            Div(children=[Text(content="x", on_key=key_handler_capturing("x"))]),
            Div(children=[Text(content="x", on_key=key_handler_capturing("y"))]),
            id="elements-holding-different-handlers",
        ),
        pytest.param(Text(content="x"), Text(content="y"), id="elements-with-different-content"),
        pytest.param((1, 2), (1, 2, 3), id="tuples-of-different-lengths"),
        pytest.param({"k": 1}, {"j": 1}, id="dicts-with-different-keys"),
    ],
)
def test_not_equivalent(a: object, b: object) -> None:
    assert not equivalent(a, b)
