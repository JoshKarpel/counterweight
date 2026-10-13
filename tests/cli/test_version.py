import runpy
import sys

import pytest
from typer.testing import CliRunner

from counterweight.cli import cli
from counterweight.constants import PACKAGE_NAME, __version__


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ("version",))

    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_via_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", [PACKAGE_NAME, "version"])

    with pytest.raises(SystemExit) as exit:
        runpy.run_module(PACKAGE_NAME, run_name="__main__")

    assert exit.value.code == 0
    assert __version__ in capsys.readouterr().out
