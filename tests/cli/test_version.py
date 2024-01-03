import subprocess
import sys

import pytest
from typer.testing import CliRunner

from counterweight.cli import cli
from counterweight.constants import PACKAGE_NAME, __version__


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ("version",))

    assert result.exit_code == 0
    assert __version__ in result.stdout


@pytest.mark.slow
def test_version_via_main() -> None:
    result = subprocess.run((sys.executable, "-m", PACKAGE_NAME, "version"), check=False, capture_output=True)

    assert result.returncode == 0
    assert __version__ in result.stdout.decode()
