import io
import json
import logging
from asyncio import Event
from asyncio import TaskGroup
from asyncio import get_running_loop
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import get_clock_info
from traceback import TracebackException

import pytest
from without_logging import exception_to_dict

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Text
from counterweight.logging import BASE_LOG_LEVELS
from counterweight.logging import TAIL_POLL
from counterweight.logging import app_log_levels
from counterweight.logging import devlog
from counterweight.logging import format_line
from counterweight.logging import last_devlog
from counterweight.logging import render_exception
from counterweight.logging import render_line
from counterweight.logging import tail_devlog
from counterweight.logging import wait_for_more

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


def captured(path: Path) -> list[tuple[str, str, str]]:
    return [
        (record["logger"], record["level"], record["message"])
        for record in map(json.loads, path.read_text().splitlines())
    ]


async def test_devlog_writes_each_record_as_a_json_line(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"
    logger = logging.getLogger("tests.test_logging")

    async with devlog(path, levels={"tests": logging.DEBUG}):
        logger.debug("First", extra={"answer": 42})
        logger.info("Second")

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [(record["level"], record["message"]) for record in records] == [("DEBUG", "First"), ("INFO", "Second")]
    assert records[0]["answer"] == 42


async def test_devlog_captures_counterweight_at_every_level_and_others_from_info_by_default(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"

    async with devlog(path):
        logging.getLogger("counterweight.app").debug("Ours")
        logging.getLogger("some_library.parser").debug("Chatty")
        logging.getLogger("some_library.parser").info("Notable")

    assert captured(path) == [
        ("counterweight.app", "DEBUG", "Ours"),
        ("some_library.parser", "INFO", "Notable"),
    ]


async def test_devlog_skips_records_below_their_level_before_building_them(tmp_path: Path) -> None:
    async with devlog(tmp_path / "devlog.jsonl"):
        assert not logging.getLogger("some_library").isEnabledFor(logging.DEBUG)
        assert logging.getLogger("counterweight.markdown").isEnabledFor(logging.DEBUG)


async def test_devlog_levels_override_by_logger_name(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"

    async with devlog(path, levels=BASE_LOG_LEVELS | {"my_app": logging.DEBUG, "counterweight": logging.WARNING}):
        logging.getLogger("my_app.views").debug("Mine")
        logging.getLogger("counterweight.app").info("Quiet")
        logging.getLogger("other").debug("Chatty")

    assert captured(path) == [("my_app.views", "DEBUG", "Mine")]


@pytest.mark.parametrize("levels", [{"named": logging.INFO, "other": logging.DEBUG}, {}])
async def test_unnamed_root_captures_from_the_lowest_level(tmp_path: Path, levels: dict[str, int]) -> None:
    path = tmp_path / "devlog.jsonl"

    async with devlog(path, levels=levels):
        logging.getLogger("anyone").debug("Debug")

    assert captured(path) == [("anyone", "DEBUG", "Debug")]


async def test_devlog_restores_logger_levels_on_exit(tmp_path: Path) -> None:
    root, named = logging.getLogger(), logging.getLogger("counterweight")
    before = (root.level, named.level)

    async with devlog(tmp_path / "devlog.jsonl"):
        assert (root.level, named.level) == (logging.INFO, logging.DEBUG)

    assert (root.level, named.level) == before


async def test_a_devlog_opened_inside_another_on_the_same_path_keeps_its_records(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"
    logger = logging.getLogger("counterweight.outer")

    async with devlog(path):
        logger.info("Before")
        async with devlog(path):
            logger.info("Inside")
        logger.info("After")

    assert captured(path) == [
        ("counterweight.outer", "INFO", "Before"),
        ("counterweight.outer", "INFO", "Inside"),
        ("counterweight.outer", "INFO", "After"),
    ]


async def test_a_devlog_opened_inside_another_on_the_same_path_captures_through_the_same_handler(
    tmp_path: Path,
) -> None:
    path = tmp_path / "devlog.jsonl"
    root = logging.getLogger()

    async with devlog(path):
        outer_handlers = list(root.handlers)
        async with devlog(path):
            inner_handlers = list(root.handlers)

    assert inner_handlers == outer_handlers


async def test_a_devlog_opened_inside_another_keeps_the_first_ones_levels(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"

    async with devlog(path), devlog(path, levels={"": logging.DEBUG}):
        logging.getLogger("some_library").debug("Chatty")
        logging.getLogger("some_library").info("Notable")

    assert captured(path) == [("some_library", "INFO", "Notable")]


async def test_a_devlog_on_another_path_opens_its_own(tmp_path: Path) -> None:
    outer, inner = tmp_path / "outer.jsonl", tmp_path / "inner.jsonl"

    async with devlog(outer):
        async with devlog(inner):
            logging.getLogger("counterweight").info("Both")
        logging.getLogger("counterweight").info("Outer only")

    assert (captured(outer), captured(inner)) == (
        [("counterweight", "INFO", "Both"), ("counterweight", "INFO", "Outer only")],
        [("counterweight", "INFO", "Both")],
    )


async def test_a_shared_devlog_captures_until_the_last_block_exits_whichever_entered_first(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"
    logger = logging.getLogger("counterweight")
    first_entered, second_entered, first_exited = Event(), Event(), Event()

    async def first() -> None:
        async with devlog(path):
            first_entered.set()
            await second_entered.wait()
        first_exited.set()

    async def second() -> None:
        await first_entered.wait()
        async with devlog(path):
            second_entered.set()
            await first_exited.wait()
            logger.info("Still open")
        logger.info("Closed")

    async with TaskGroup() as task_group:
        task_group.create_task(first())
        task_group.create_task(second())

    assert captured(path) == [("counterweight", "INFO", "Still open")]


async def test_a_devlog_closes_with_its_last_block(tmp_path: Path) -> None:
    handlers = list(logging.getLogger().handlers)

    async with devlog(tmp_path / "devlog.jsonl"), devlog(tmp_path / "devlog.jsonl"):
        pass

    assert logging.getLogger().handlers == handlers


async def test_a_devlog_that_fails_to_open_is_opened_afresh_next_time(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "devlog.jsonl"
    with pytest.raises(FileNotFoundError):
        async with devlog(path):
            pass  # pragma: never runs
    path.parent.mkdir()

    async with devlog(path):
        logging.getLogger("counterweight").info("Opened")

    assert captured(path) == [("counterweight", "INFO", "Opened")]


class StopTailing(Exception):
    pass


def json_line(message: str) -> str:
    return json.dumps({**RECORD, "message": message}) + "\n"


def scripted_wait(*steps: Callable[[], None]) -> Callable[[], Awaitable[None]]:
    """A `wait` for `tail_devlog` that runs the next step each time it's awaited, then stops tailing."""
    remaining = iter(steps)

    async def wait() -> None:
        next(remaining, raise_stop)()

    return wait


def raise_stop() -> None:
    raise StopTailing


async def stop() -> None:
    raise_stop()


@pytest.mark.parametrize("raw", [True, False])
async def test_tail_devlog_writes_each_line_once_it_is_complete(tmp_path: Path, raw: bool) -> None:
    path = tmp_path / "devlog.jsonl"
    first, second = json_line("First"), json_line("Second")
    path.write_text(first + second[:10])

    def finish_second() -> None:
        with path.open("a") as f:
            f.write(second[10:])

    out = io.StringIO()
    with pytest.raises(StopTailing):
        await tail_devlog(out, raw=raw, path=path, wait=scripted_wait(finish_second))

    assert out.getvalue() == f"{format_line(first, raw)}\n{format_line(second, raw)}\n"


async def test_tail_devlog_starts_over_when_the_devlog_is_truncated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "24")
    path = tmp_path / "devlog.jsonl"
    path.write_text("a long first line\n")

    def truncate() -> None:
        path.write_text("next\n")

    out = io.StringIO()
    with pytest.raises(StopTailing):
        await tail_devlog(out, raw=True, path=path, wait=scripted_wait(truncate))

    assert out.getvalue() == "a long first line\n━━━━ DevLog Rotated ━━━━\nnext\n"


async def test_tail_devlog_creates_a_missing_devlog(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"

    with pytest.raises(StopTailing):
        await tail_devlog(io.StringIO(), path=path, wait=stop)

    assert path.read_text() == ""


async def test_tail_devlog_waits_one_poll_on_the_event_loop_by_default() -> None:
    loop = get_running_loop()
    start = loop.time()

    await wait_for_more()

    # The loop runs a timer up to its clock's resolution early.
    assert loop.time() - start >= TAIL_POLL.total_seconds() - get_clock_info("monotonic").resolution


@pytest.mark.parametrize("raw", [True, False])
def test_last_devlog_writes_the_last_complete_lines(tmp_path: Path, raw: bool) -> None:
    path = tmp_path / "devlog.jsonl"
    lines = [json_line(message) for message in ("First", "Second", "Third")]
    path.write_text("".join(lines) + '{"incomplete')

    out = io.StringIO()
    last_devlog(out, 2, raw=raw, path=path)

    assert out.getvalue() == f"{format_line(lines[1], raw)}\n{format_line(lines[2], raw)}\n"


def test_last_devlog_creates_a_missing_devlog(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"
    out = io.StringIO()

    last_devlog(out, 3, path=path)

    assert (path.read_text(), out.getvalue()) == ("", "")


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


async def test_tail_devlog_renders_lines_by_default(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"
    line = json_line("First")
    path.write_text(line)
    out = io.StringIO()

    with pytest.raises(StopTailing):
        await tail_devlog(out, path=path, wait=stop)

    assert out.getvalue() == format_line(line, raw=False) + "\n"


def test_last_devlog_renders_lines_by_default(tmp_path: Path) -> None:
    path = tmp_path / "devlog.jsonl"
    line = json_line("First")
    path.write_text(line)
    out = io.StringIO()

    last_devlog(out, 1, path=path)

    assert out.getvalue() == format_line(line, raw=False) + "\n"


@pytest.mark.parametrize(
    ("module", "package"),
    [("__main__", "__main__"), ("my_app", "my_app"), ("my_app.ui.screens", "my_app")],
)
def test_app_log_levels_capture_the_apps_top_level_package_at_debug(module: str, package: str) -> None:
    assert app_log_levels(module, {}) == BASE_LOG_LEVELS | {package: logging.DEBUG}


def test_app_log_levels_overrides_win_over_the_base_and_the_app() -> None:
    overrides = {"": logging.WARNING, "my_app": logging.INFO, "some_library": logging.DEBUG}

    assert app_log_levels("my_app.ui", overrides) == {
        "": logging.WARNING,
        "counterweight": logging.DEBUG,
        "my_app": logging.INFO,
        "some_library": logging.DEBUG,
    }


@pytest.mark.parametrize(
    ("overrides", "is_debug_enabled"),
    [({}, True), ({"tests": logging.INFO}, False)],
)
async def test_app_captures_its_root_components_package_at_debug(
    overrides: dict[str, int], is_debug_enabled: bool
) -> None:
    seen: list[bool] = []

    @component
    def root() -> Text:
        seen.append(logging.getLogger("tests.anything").isEnabledFor(logging.DEBUG))
        return Text(content="")

    await app(root(), headless=True, dimensions=(4, 1), autopilot=[Quit()], log_levels=overrides)

    assert seen[0] is is_debug_enabled
