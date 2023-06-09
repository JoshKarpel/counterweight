from textwrap import dedent

from click import echo
from typer import Typer

from reprisal.constants import PACKAGE_NAME, __version__

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


# dummy callback to force subcommands, can be removed once a second subcommand is added
@cli.callback()
def callback() -> None:
    pass
