from pytest_mock import MockerFixture

from reprisal.hooks import Anchor, use_effect


def test_callback_is_called_every_time_if_no_deps(mocker: MockerFixture) -> None:
    mock = mocker.Mock()

    def _() -> None:
        use_effect(mock)

    ctx = Anchor(_)

    ctx()
    assert mock.call_count == 1

    ctx()
    assert mock.call_count == 2

    ctx()
    assert mock.call_count == 3


def test_callback_is_called_based_on_whether_dependencies_changed(mocker: MockerFixture) -> None:
    mock = mocker.Mock()
    deps = (0,)  # you wouldn't normally mutate it like this...

    def _() -> None:
        nonlocal deps
        use_effect(mock, deps)

    anchor = Anchor(_)

    anchor()
    assert mock.call_count == 1

    anchor()
    assert mock.call_count == 1

    deps = (1,)

    anchor()
    assert mock.call_count == 2

    anchor()
    assert mock.call_count == 2

    deps = (2,)

    anchor()
    assert mock.call_count == 3

    anchor()
    assert mock.call_count == 3
