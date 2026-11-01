"""
The installed version, kept apart from `_constants` because looking it up imports `importlib.metadata`
and reads the installed packages, which `counterweight` defers until something reads `__version__`.
"""

from importlib import metadata

from counterweight._constants import PACKAGE_NAME

__version__ = metadata.version(PACKAGE_NAME)
"""The version of counterweight that's installed, such as `"0.1.0"`."""
