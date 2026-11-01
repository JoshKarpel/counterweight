import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "importlib.metadata",
        "without_cli",
        "counterweight.gradients",
        "counterweight.programs",
        "counterweight.asciicast",
        "counterweight.painters",
        "counterweight.emulator",
        "evp",
    ],
)
def test_importing_counterweight_leaves_what_only_some_apps_use_unimported(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import sys, counterweight; print({module!r} in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
        # Without coverage, which `patch = ["subprocess"]` starts in every child and which imports importlib.metadata.
        env={name: value for name, value in os.environ.items() if name != "COVERAGE_PROCESS_CONFIG"},
    )

    assert result.stdout.strip() == "False"
