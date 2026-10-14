import runpy
import sys

import pytest
from without_cli import Streams
from without_cli import run

from counterweight.cli import cli
from counterweight.constants import PACKAGE_NAME
from counterweight.constants import __version__


@pytest.mark.parametrize("argv", [("version",), ("--version",)])
def test_version(argv: tuple[str, ...]) -> None:
    capture = Streams.captured()

    code = run(cli, argv=argv, streams=capture.streams)

    assert code == 0
    assert capture.stdout == f"{__version__}\n"


def test_version_via_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", [PACKAGE_NAME, "version"])

    with pytest.raises(SystemExit) as exited:
        runpy.run_module(PACKAGE_NAME, run_name="__main__")

    assert exited.value.code == 0
    assert __version__ in capsys.readouterr().out
