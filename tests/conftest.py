import os
import resource
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

MUTANT_MEMORY_HEADROOM = 1 << 30


def pytest_configure(config: pytest.Config) -> None:
    if "__mutmut_" in os.environ.get("MUTANT_UNDER_TEST", "") and sys.platform == "linux":
        cap_address_space(headroom=MUTANT_MEMORY_HEADROOM)


def cap_address_space(headroom: int) -> None:
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
def runner() -> CliRunner:
    return CliRunner()
