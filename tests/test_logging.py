import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from traceback import TracebackException

import pytest
from without_logging import exception_to_dict

from counterweight.logging import devlog, format_line, last_devlog, render_exception, render_line, tail_devlog

RECORD = {
    "timestamp": "2026-10-11T03:16:34.779176+00:00",
    "level": "DEBUG",
    "logger": "counterweight.app",
    "message": "Diffed new paint from current paint",
    "diff_cells": 7,
    "handler": "on_key",
}


def test_render_line_shows_local_time_level_logger_message_and_fields() -> None:
    local_time = datetime.fromisoformat(str(RECORD["timestamp"])).astimezone().strftime("%H:%M:%S.%f")

    assert render_line(RECORD) == (
        f"{local_time} DEBUG    counterweight.app Diffed new paint from current paint diff_cells=7 handler='on_key'"
    )


def test_render_line_appends_the_traceback_with_its_cause_first() -> None:
    try:
        try:
            raise KeyError("inner")
        except KeyError as inner:
            raise ValueError("outer") from inner
    except ValueError as outer:
        exception = exception_to_dict(TracebackException.from_exception(outer))

    lines = render_line({**RECORD, "exception": exception}).splitlines()

    assert lines[1] == "  Traceback (most recent call last):"
    assert "  KeyError: 'inner'" in lines
    assert lines[-1] == "  ValueError: outer"
    assert lines.index("  KeyError: 'inner'") < lines.index("  The above exception led to the following exception:")


async def test_devlog_writes_every_record_as_a_json_line(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"
    logger = logging.getLogger("tests.test_logging")

    async with devlog(path):
        logger.debug("First", extra={"answer": 42})
        logger.info("Second")

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [(record["level"], record["message"]) for record in records] == [("DEBUG", "First"), ("INFO", "Second")]
    assert records[0]["answer"] == 42


class StopTailing(Exception):
    pass


def json_line(message: str) -> str:
    return json.dumps({**RECORD, "message": message}) + "\n"


def scripted_wait(*steps: Callable[[], None]) -> Callable[[], None]:
    """A `wait` for `tail_devlog` that runs the next step each time it's called, then stops tailing."""
    remaining = iter(steps)

    def wait() -> None:
        next(remaining, stop)()

    return wait


def stop() -> None:
    raise StopTailing


@pytest.mark.parametrize("raw", [True, False])
def test_tail_devlog_prints_each_line_once_it_is_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], raw: bool
) -> None:
    path = tmp_path / "devlog.jsonl"
    first, second = json_line("First"), json_line("Second")
    path.write_text(first + second[:10])

    def finish_second() -> None:
        with path.open("a") as f:
            f.write(second[10:])

    with pytest.raises(StopTailing):
        tail_devlog(raw=raw, path=path, wait=scripted_wait(finish_second))

    assert capsys.readouterr().out == f"{format_line(first, raw)}\n{format_line(second, raw)}\n"


def test_tail_devlog_starts_over_when_the_devlog_is_truncated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "24")
    path = tmp_path / "devlog.jsonl"
    path.write_text("a long first line\n")

    def truncate() -> None:
        path.write_text("next\n")

    with pytest.raises(StopTailing):
        tail_devlog(raw=True, path=path, wait=scripted_wait(truncate))

    assert capsys.readouterr().out == "a long first line\n━━━━ DevLog Rotated ━━━━\nnext\n"


def test_tail_devlog_creates_a_missing_devlog(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"

    with pytest.raises(StopTailing):
        tail_devlog(path=path, wait=stop)

    assert path.read_text() == ""


@pytest.mark.parametrize("raw", [True, False])
def test_last_devlog_prints_the_last_complete_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], raw: bool
) -> None:
    path = tmp_path / "devlog.jsonl"
    lines = [json_line(message) for message in ("First", "Second", "Third")]
    path.write_text("".join(lines) + '{"incomplete')

    last_devlog(2, raw=raw, path=path)

    assert capsys.readouterr().out == f"{format_line(lines[1], raw)}\n{format_line(lines[2], raw)}\n"


def test_last_devlog_creates_a_missing_devlog(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "devlog.jsonl"

    last_devlog(3, path=path)

    assert (path.read_text(), capsys.readouterr().out) == ("", "")


@pytest.mark.parametrize("line", ["ends in spaces \t ", "ends in X"])
def test_format_line_strips_only_the_newline_from_a_raw_line(line: str) -> None:
    assert format_line(line + "\n", raw=True) == line


def test_format_line_renders_a_parsed_line() -> None:
    assert format_line(json.dumps(RECORD) + "\n", raw=False) == render_line(RECORD)


def test_render_exception_prints_each_frame_and_its_code_after_its_cause() -> None:
    exception = {
        "message": "ValueError: outer",
        "frames": [
            {"file": "app.py", "line": 12, "function": "handle", "code": "raise ValueError('outer')"},
            {"file": "<string>", "line": 1, "function": "<module>", "code": ""},
        ],
        "cause": {
            "message": "KeyError: 'inner'",
            "frames": [{"file": "lookup.py", "line": 3, "function": "find", "code": "table[key]"}],
        },
    }

    assert render_exception(exception) == [
        "Traceback (most recent call last):",
        '  File "lookup.py", line 3, in find',
        "    table[key]",
        "KeyError: 'inner'",
        "",
        "The above exception led to the following exception:",
        "",
        "Traceback (most recent call last):",
        '  File "app.py", line 12, in handle',
        "    raise ValueError('outer')",
        '  File "<string>", line 1, in <module>',
        "ValueError: outer",
    ]


def test_tail_devlog_renders_lines_by_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "devlog.jsonl"
    line = json_line("First")
    path.write_text(line)

    with pytest.raises(StopTailing):
        tail_devlog(path=path, wait=stop)

    assert capsys.readouterr().out == format_line(line, raw=False) + "\n"


def test_last_devlog_renders_lines_by_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "devlog.jsonl"
    line = json_line("First")
    path.write_text(line)

    last_devlog(1, path=path)

    assert capsys.readouterr().out == format_line(line, raw=False) + "\n"
