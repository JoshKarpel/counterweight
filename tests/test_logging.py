import json
import logging
from datetime import datetime
from pathlib import Path
from traceback import TracebackException

from without_logging import exception_to_dict

from counterweight.logging import devlog, render_line

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
