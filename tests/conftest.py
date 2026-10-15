import asyncio
import gc
import inspect
import os
import pty
import resource
import signal
import subprocess
import sys
from collections.abc import AsyncIterator
from collections.abc import Iterator
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from threading import Thread

import pytest

from tests.terminal import Terminal

MUTANT_MEMORY_HEADROOM = 1 << 30

HANG_REPORT_LEAD = 5
"""How many seconds before `faulthandler_timeout` an async test still running reports what it's waiting on."""

LRU_CACHE = type(lru_cache(lambda: None))


def pytest_configure(config: pytest.Config) -> None:
    # Only mutmut's workers prepare themselves, so the suite never runs this, or the two functions below.
    if "__mutmut_" in os.environ.get("MUTANT_UNDER_TEST", ""):  # pragma: no cover
        clear_memos()
        if sys.platform == "linux":
            cap_address_space(headroom=MUTANT_MEMORY_HEADROOM)


@pytest.fixture(autouse=True)
def cold_memos_while_mutmut_maps_tests() -> None:
    """
    Empties every counterweight cache before each test in mutmut's stats pass, which maps each function to the tests
    that run it: a function reached only through a cache would otherwise be mapped only to the tests that missed it,
    and only those would run against its mutants.
    """
    if os.environ.get("MUTANT_UNDER_TEST") == "stats":  # pragma: no cover
        clear_memos()


@pytest.fixture(autouse=True)
def editor_that_fails_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Makes the preferred editor `false` for tests that don't set their own, so code that wrongly falls back to it,
    as a mutant of `edit_file` can, fails the test at once rather than opening the developer's editor
    on a stream that isn't a terminal, where it waits forever, and outlives a mutmut worker killed for timing out.
    """
    monkeypatch.setenv("VISUAL", "false")
    monkeypatch.setenv("EDITOR", "false")


@pytest.fixture(autouse=True)
def hang_report_for_async_tests(request: pytest.FixtureRequest) -> None:
    """Gives every async test a `hang_report`, which needs the test's event loop, and so has to be async itself."""
    if inspect.iscoroutinefunction(getattr(request.node, "obj", None)):
        request.getfixturevalue("hang_report")


@pytest.fixture
async def hang_report(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """
    Reports what a test is waiting on `HANG_REPORT_LEAD` seconds before `faulthandler_timeout` would end the whole run.
    faulthandler dumps only threads, where a hung async test is an event loop idle in `select`,
    and a run it ends shows none of the test's captured output.
    So this reports each task's await chain, every process group the test signalled, and the processes still running,
    then cancels the test's tasks, so the test fails with the report as its captured output, and the run goes on.
    """
    loop = asyncio.get_running_loop()
    signalled: list[tuple[str, int]] = []
    killpg = os.killpg

    def recording_killpg(group: int, signal_number: int) -> None:
        call = f"{loop.time():.3f} killpg({group}, {signal.Signals(signal_number).name if signal_number else 0})"
        try:
            killpg(group, signal_number)
        except OSError as e:
            signalled.append((f"{call} raised {e!r}", group))
            raise
        signalled.append((call, group))

    monkeypatch.setattr(os, "killpg", recording_killpg)
    timeout = float(request.config.getini("faulthandler_timeout"))
    report = loop.call_later(timeout - HANG_REPORT_LEAD, report_hang, signalled)
    yield
    report.cancel()


def report_hang(signalled: list[tuple[str, int]]) -> None:  # pragma: no cover, runs only in a test that hangs
    """
    Prints what `hang_report` reports, then cancels every task, which fails the test that hung.
    The processes it lists are the test process's children and everything in their process groups or in a group
    the test signalled, which a program run in its own session, and anything it started, are.
    """
    print(f"{asyncio.get_running_loop().time():.3f} The test is about to time out. Its tasks:", file=sys.stderr)
    for task in asyncio.all_tasks():
        asyncio.print_call_graph(task, file=sys.stderr)
    print("Process groups it signalled:", *(call for call, _ in signalled), sep="\n  ", file=sys.stderr)
    listing = subprocess.run(
        ["ps", "-A", "-o", "pid=,ppid=,pgid=,stat=,command="], capture_output=True, text=True, check=False
    ).stdout.splitlines()
    rows = [(line, line.split()) for line in listing if len(line.split()) >= 5]
    groups = {fields[2] for _, fields in rows if fields[1] == str(os.getpid())} | {str(g) for _, g in signalled}
    related = [line for line, fields in rows if fields[1] == str(os.getpid()) or fields[2] in groups]
    print("Its processes (pid, ppid, pgid, state, command):", *related, sep="\n  ", file=sys.stderr)
    for task in asyncio.all_tasks():
        task.cancel()


def clear_memos() -> None:  # pragma: no cover
    """
    Empties every `lru_cache` in counterweight, including the ones behind `flyweight` classes.
    A mutmut worker forks from mutmut's parent process after it has run every test, so each cache is warm,
    and a mutant of a function that only runs on a cache miss (such as `justify_line`, behind `line_cells`)
    would never run at all; `cold_memos_while_mutmut_maps_tests` empties them for the same reason.
    mutmut freezes its heap before forking a worker, and `gc.get_objects` skips frozen objects, so this unfreezes first.
    """
    gc.unfreeze()
    for candidate in gc.get_objects():
        if isinstance(candidate, LRU_CACHE) and candidate.__module__.startswith("counterweight"):
            candidate.cache_clear()


def cap_address_space(headroom: int) -> None:  # pragma: no cover
    """
    Caps this process's address space at its current size plus `headroom`, so allocating past it raises `MemoryError`.
    A mutant can turn a loop into one that never advances and appends on every pass,
    allocating hundreds of megabytes a second, which exhausts the machine long before mutmut's timeout fires.
    Capped, each mutmut worker fails its tests instead, which counts the mutant as killed.
    `RLIMIT_AS` is enforced on Linux, and the cap is relative because a worker forks from mutmut's parent process,
    inheriting its address space.
    """
    pages = int(Path("/proc/self/statm").read_text().split()[0])
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (pages * resource.getpagesize() + headroom, hard))


def read_until_closed(keyboard: int) -> None:
    """
    Reads everything the program side of a pseudo-terminal writes, as a terminal emulator would,
    until the program side closes.
    That includes the echo of keys a test types before input control turns echo off,
    and on macOS `tcsetattr(..., TCSADRAIN)` waits for that echo to be read, so without this it blocks forever.
    """
    # Linux raises EIO once the program side closes, rather than reading the end of the input.
    with suppress(OSError):
        while os.read(keyboard, 2**10):  # pragma: no branch
            pass


@pytest.fixture
def terminal() -> Iterator[Terminal]:
    keyboard, program = pty.openpty()
    screen = Thread(target=read_until_closed, args=(keyboard,))
    screen.start()
    with os.fdopen(program) as stream:
        yield Terminal(stream=stream, keyboard=keyboard)
    screen.join()
    os.close(keyboard)
