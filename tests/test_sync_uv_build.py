"""The `uv_build` build requirement follows the uv that `mise.lock` pins, through that uv's patch releases."""

from __future__ import annotations

import pytest

from codegen.sync_uv_build import build_requirement
from codegen.sync_uv_build import pinned_uv_version
from codegen.sync_uv_build import with_build_requirement

PYPROJECT = """\
[build-system]
requires = ["uv_build>=0.12.23,<0.13"]
build-backend = "uv_build"

[project]
name = "counterweight"
"""


def test_pinned_uv_version_is_read_from_the_lock() -> None:
    mise_lock = """\
[[tools.just]]
version = "1.58.0"

[[tools.uv]]
version = "0.14.2"
backend = "aqua:astral-sh/uv"
"""

    assert pinned_uv_version(mise_lock) == "0.14.2"


@pytest.mark.parametrize(
    ("uv_version", "requirement"),
    [
        ("0.13.0", "uv_build>=0.13.0,<0.14"),
        ("0.9.17", "uv_build>=0.9.17,<0.10"),
        ("1.2.3", "uv_build>=1.2.3,<1.3"),
    ],
)
def test_requirement_allows_the_pinned_minors_patch_releases(uv_version: str, requirement: str) -> None:
    assert build_requirement(uv_version) == requirement


def test_only_the_build_requirement_changes() -> None:
    assert with_build_requirement(PYPROJECT, "uv_build>=0.13.4,<0.14") == PYPROJECT.replace(
        "uv_build>=0.12.23,<0.13", "uv_build>=0.13.4,<0.14"
    )


def test_a_pyproject_without_the_build_requirement_fails() -> None:
    with pytest.raises(ValueError, match="found 0"):
        with_build_requirement('[build-system]\nrequires = ["hatchling"]\n', "uv_build>=0.13.4,<0.14")
