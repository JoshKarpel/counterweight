import subprocess
import sys

from typer.testing import CliRunner

from counterweight.cli import cli
from counterweight.constants import PACKAGE_NAME


def test_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0


def test_help_via_main() -> None:
    result = subprocess.run([sys.executable, "-m", PACKAGE_NAME, "--help"], check=False)

    assert result.returncode == 0
