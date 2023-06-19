from __future__ import annotations

from textwrap import dedent

from click import echo
from typer import Typer

from reprisal.constants import PACKAGE_NAME, __version__
from reprisal.logging import tail_devlog

cli = Typer(
    name=PACKAGE_NAME,
    no_args_is_help=True,
    rich_markup_mode="rich",
    help=dedent(
        """\
        """
    ),
)


@cli.command()
def version() -> None:
    """
    Display version information.
    """
    echo(__version__)


@cli.command()
def devlog() -> None:
    tail_devlog()


# dummy callback to force subcommands, can be removed once a second subcommand is added
@cli.callback()
def callback() -> None:
    pass
