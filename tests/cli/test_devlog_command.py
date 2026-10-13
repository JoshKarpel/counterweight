import pytest
from without_cli import Streams, Writer, run

from counterweight.cli import cli


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("devlog",), ("tail", ("raw", False))),
        (("devlog", "--json"), ("tail", ("raw", True))),
        (("devlog", "--last", "3"), ("last", 3, ("raw", False))),
        (("devlog", "--last", "3", "--json"), ("last", 3, ("raw", True))),
    ],
)
def test_devlog_tails_the_devlog_or_prints_its_last_lines(
    monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...], expected: tuple[object, ...]
) -> None:
    capture = Streams.captured()
    calls: list[tuple[object, ...]] = []

    async def tail(out: Writer, **kwargs: object) -> None:
        calls.append(("tail", out, *sorted(kwargs.items())))

    def last(out: Writer, n: int, **kwargs: object) -> None:
        calls.append(("last", out, n, *sorted(kwargs.items())))

    monkeypatch.setattr("counterweight.cli.tail_devlog", tail)
    monkeypatch.setattr("counterweight.cli.last_devlog", last)

    code = run(cli, argv=argv, streams=capture.streams)

    name, *arguments = expected
    assert (code, calls) == (0, [(name, capture.out, *arguments)])
