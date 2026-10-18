"""
Add the favicon's PNGs to the site at `assets/logo/`, drawn by `codegen.generate_logo.icons` when the site is built.

The repository holds only the logo's SVGs, which are text and come out byte-identical on every platform;
the PNGs' bytes depend on which zlib-ng build Pillow compresses with.
"""

import sys
from io import BytesIO
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import File
from mkdocs.structure.files import Files

# While it loads a hook, mkdocs puts only the hook's own directory on the path.
sys.path.insert(0, str(Path(__file__).parent.parent))
from codegen.generate_logo import icons


def on_files(files: Files, /, *, config: MkDocsConfig) -> Files:
    for name, image in icons().items():
        png = BytesIO()
        image.save(png, format="PNG", optimize=True)
        files.append(File.generated(config, f"assets/logo/{name}", content=png.getvalue()))
    return files
