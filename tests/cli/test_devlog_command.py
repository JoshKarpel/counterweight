from collections.abc import Callable

import pytest
from typer.testing import CliRunner

from counterweight.cli import cli


def recorder(calls: list[tuple[object, ...]], name: str) -> Callable[..., None]:
    def record(*args: object, **kwargs: object) -> None:
        calls.append((name, *args, *sorted(kwargs.items())))

    return record


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["devlog"], ("tail", ("raw", False))),
        (["devlog", "--json"], ("tail", ("raw", True))),
        (["devlog", "--last", "3"], ("last", 3, ("raw", False))),
        (["devlog", "--last", "3", "--json"], ("last", 3, ("raw", True))),
    ],
)
def test_devlog_tails_the_devlog_or_prints_its_last_lines(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, arguments: list[str], expected: tuple[object, ...]
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("counterweight.cli.tail_devlog", recorder(calls, "tail"))
    monkeypatch.setattr("counterweight.cli.last_devlog", recorder(calls, "last"))

    result = runner.invoke(cli, arguments)

    assert (result.exit_code, calls) == (0, [expected])
