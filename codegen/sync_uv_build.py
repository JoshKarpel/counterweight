#!/usr/bin/env python3
"""
Keeps `pyproject.toml`'s `uv_build` requirement at the uv that `mise.lock` pins,
so `uv build` uses the backend built into that uv instead of installing a separate `uv_build` to build with.

uv bumps its minor version for breaking changes, so the requirement allows the pinned version's patch releases and no further.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from more_itertools import one

ROOT = Path(__file__).parent.parent
MISE_LOCK = ROOT / "mise.lock"
PYPROJECT = ROOT / "pyproject.toml"

BUILD_REQUIRES = re.compile(r'^requires = \["uv_build[^"]*"\]$', flags=re.MULTILINE)


def pinned_uv_version(mise_lock: str) -> str:
    """The version of uv that `mise.lock` resolves, which must be exactly one."""
    return str(one(tomllib.loads(mise_lock)["tools"]["uv"])["version"])


def build_requirement(uv_version: str) -> str:
    """The `uv_build` requirement that the given uv's built-in backend satisfies, through its last patch release."""
    major, minor, *_ = uv_version.split(".")
    return f"uv_build>={uv_version},<{major}.{int(minor) + 1}"


def with_build_requirement(pyproject: str, requirement: str) -> str:
    """`pyproject` with its `[build-system]` requirement replaced, which raises unless there is exactly one to replace."""
    synced, count = BUILD_REQUIRES.subn(f'requires = ["{requirement}"]', pyproject)
    if count != 1:
        raise ValueError(f"Expected one `uv_build` build requirement in pyproject.toml, found {count}")
    return synced


def main() -> None:
    pyproject = PYPROJECT.read_text()
    synced = with_build_requirement(pyproject, build_requirement(pinned_uv_version(MISE_LOCK.read_text())))

    if synced == pyproject:
        print("The uv_build requirement matches the pinned uv")
        return

    PYPROJECT.write_text(synced)
    print(f"Synced the uv_build requirement in {PYPROJECT} to the uv that {MISE_LOCK} pins")


if __name__ == "__main__":
    main()
