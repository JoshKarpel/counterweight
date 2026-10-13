import subprocess
import sys

import pytest
from without_cli import Streams, run

from counterweight.cli import cli
from counterweight.constants import PACKAGE_NAME


def test_help() -> None:
    capture = Streams.captured()

    code = run(cli, argv=("--help",), streams=capture.streams)

    assert code == 0
    assert "check-input" in capture.stdout


@pytest.mark.slow
def test_help_via_main() -> None:
    result = subprocess.run((sys.executable, "-m", PACKAGE_NAME, "--help"), check=False)

    assert result.returncode == 0
