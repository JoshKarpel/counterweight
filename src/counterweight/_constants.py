from __future__ import annotations

import sys
from importlib import metadata

PACKAGE_NAME = "counterweight"
__version__ = metadata.version(PACKAGE_NAME)
__python_version__ = ".".join(map(str, sys.version_info))
