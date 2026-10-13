import subprocess
import sys

import pytest
from without_cli import Streams, run

from counterweight.cli import cli
from counterweight.constants import PACKAGE_NAME, __version__


@pytest.mark.parametrize("argv", [("version",), ("--version",)])
def test_version(argv: tuple[str, ...]) -> None:
    capture = Streams.captured()

    code = run(cli, argv=argv, streams=capture.streams)

    assert code == 0
    assert capture.stdout == f"{__version__}\n"


@pytest.mark.slow
def test_version_via_main() -> None:
    result = subprocess.run((sys.executable, "-m", PACKAGE_NAME, "version"), check=False, capture_output=True)

    assert result.returncode == 0
    assert __version__ in result.stdout.decode()
