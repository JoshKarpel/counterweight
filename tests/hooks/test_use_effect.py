from pytest_mock import MockerFixture

from reprisal.hooks import HookContext, use_effect


def test_callback_is_called_every_time_if_no_deps(mocker: MockerFixture) -> None:
    mock = mocker.Mock()

    def _() -> None:
        use_effect(mock)

    ctx = HookContext(_)

    ctx()
    assert mock.call_count == 1

    ctx()
    assert mock.call_count == 2

    ctx()
    assert mock.call_count == 3


def test_callback_is_called_based_on_whether_dependencies_changed(mocker: MockerFixture) -> None:
    mock = mocker.Mock()
    deps = [0]  # you wouldn't normally mutate it like this...

    def _() -> None:
        use_effect(mock, deps)

    ctx = HookContext(_)

    ctx()
    assert mock.call_count == 1

    ctx()
    assert mock.call_count == 1

    deps[0] = 1

    ctx()
    assert mock.call_count == 2

    ctx()
    assert mock.call_count == 2

    deps[0] = 0

    ctx()
    assert mock.call_count == 3

    ctx()
    assert mock.call_count == 3
