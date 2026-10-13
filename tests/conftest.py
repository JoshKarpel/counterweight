import gc
import os
import pty
import resource
import sys
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

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


def clear_memos() -> None:  # pragma: no cover
    """
    Empties every `lru_cache` in counterweight, including the ones behind `flyweight` classes.
    A mutmut worker forks from mutmut's parent process after it has run every test, so each cache is warm,
    and a mutant of a function that only runs on a cache miss (such as `justify_line`, behind `text_lines`)
    would never run at all.
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


@pytest.fixture
def terminal() -> Iterator[Terminal]:
    keyboard, program = pty.openpty()
    with os.fdopen(program) as stream:
        yield Terminal(stream=stream, keyboard=keyboard)
    os.close(keyboard)
