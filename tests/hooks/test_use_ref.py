import pytest

from counterweight._layout import NO_LAYOUTS
from counterweight._shadow import update_shadow
from counterweight.components import component
from counterweight.elements import Text
from counterweight.hooks import Ref
from counterweight.hooks import use_ref


def make_initial() -> str:
    return "from the initializer"


@pytest.mark.parametrize(
    ("initial_value", "expected"),
    [
        pytest.param("given directly", "given directly", id="value"),
        pytest.param(make_initial, "from the initializer", id="initializer"),
    ],
)
def test_use_ref_starts_with_the_initial_value_or_what_its_initializer_returns(
    initial_value: object, expected: str
) -> None:
    refs: list[Ref[object]] = []

    @component
    def holds_ref() -> Text:
        refs.append(use_ref(initial_value))
        return Text(content="ref")

    update_shadow(holds_ref(), None, NO_LAYOUTS)

    assert refs[0].current == expected
