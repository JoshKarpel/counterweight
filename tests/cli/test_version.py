import subprocess
import sys

from typer.testing import CliRunner

from reprisal.cli import cli
from reprisal.constants import PACKAGE_NAME, __version__


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_via_main() -> None:
    result = subprocess.run([sys.executable, "-m", PACKAGE_NAME, "version"])

    assert result.returncode == 0
