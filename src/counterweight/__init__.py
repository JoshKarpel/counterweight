"""
Counterweight, a framework for terminal user interfaces inspired by React and Tailwind CSS.
The package itself holds the entry point, [`app`][counterweight.app], and each public module or subpackage one part of the API;
modules whose names start with an underscore are the framework's internals.
"""

from counterweight._app import DEFAULT_UNCLAIMED_KEYS
from counterweight._app import app
from counterweight._constants import __version__
from counterweight._viewports import FullScreen
from counterweight._viewports import Inline

__all__ = [
    "DEFAULT_UNCLAIMED_KEYS",
    "FullScreen",
    "Inline",
    "__version__",
    "app",
]
