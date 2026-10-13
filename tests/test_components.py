from typing import TYPE_CHECKING, assert_type

from counterweight.components import Component, component
from counterweight.elements import Div, Text


def repeated(label: str, count: int = 1) -> Text:
    return Text(content=label * count)


bare = component(repeated)
memoized = component(memo=True)(repeated)


if TYPE_CHECKING:
    assert_type(bare("a", count=2), Component)
    assert_type(memoized("a", count=2), Component)

    bare(1)  # type: ignore[arg-type]
    memoized(1)  # type: ignore[arg-type]
    memoized("a", size=2)  # type: ignore[call-arg]

    @component  # type: ignore[arg-type]
    def bare_returns_a_string() -> str:
        return ""

    @component(memo=True)  # type: ignore[arg-type]
    def memoized_returns_a_string() -> str:
        return ""

    component(Div, True)  # type: ignore[call-overload]


def test_bare_component_is_not_memo() -> None:
    # Decorating here rather than using the module-level `bare` makes mutation testing see `component` run.
    assert component(repeated)("a").memo is False


def test_memo_component_is_memo() -> None:
    assert memoized("a").memo is True


def test_components_with_equal_arguments_are_equal_whether_or_not_memo() -> None:
    assert bare("a") == memoized("a")
