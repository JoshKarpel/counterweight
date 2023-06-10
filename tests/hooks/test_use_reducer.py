from typing import Literal

from typing_extensions import assert_never

from reprisal.render import Root, use_reducer

CounterAction = Literal["inc", "dec", "reset"]


def counter(state: int, action: CounterAction) -> int:
    match action:
        case "inc":
            return state + 1
        case "dec":
            return state - 1
        case "reset":
            return 0
        case _:  # pragma: unreachable
            assert_never(action)


def test_counter() -> None:
    def _(action: CounterAction) -> int:
        count, dispatch = use_reducer(counter, 0)
        dispatch(action)
        return count  # previous value!

    root = Root(_)

    assert root.render("inc") == 0
    assert root.render("dec") == 1
    assert root.render("inc") == 0
    assert root.render("inc") == 1
    assert root.render("reset") == 2
    assert root.render("dec") == 0
    assert root.render("reset") == -1
