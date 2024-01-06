from counterweight.styles.utilities import *


def test_absolute() -> None:
    assert absolute(x=3, y=5) == Style(layout=Flex(position=Absolute(x=3, y=5)))
