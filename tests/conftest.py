import gc
import os
import pty
import resource
import sys
from collections.abc import Iterator
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from threading import Thread

import pytest

from tests.terminal import Terminal

MUTANT_MEMORY_HEADROOM = 1 << 30

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
