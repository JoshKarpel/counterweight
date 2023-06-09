from typing import Literal

from reprisal.hooks import Anchor, use_reducer

CounterAction = Literal["inc", "dec", "reset"]


def counter(state: int, action: CounterAction) -> int:
    match action:
        case "inc":
            return state + 1
        case "dec":
            return state - 1
        case "reset":
            return 0


def test_counter() -> None:
    def _(action: CounterAction) -> int:
        count, dispatch = use_reducer(counter, 0)
        dispatch(action)
        return count  # previous value!

    ctx = Anchor(_)

    assert ctx("inc") == 0
    assert ctx("dec") == 1
    assert ctx("inc") == 0
    assert ctx("inc") == 1
    assert ctx("reset") == 2
    assert ctx("dec") == 0
    assert ctx("reset") == -1
