from pathlib import Path

from reprisal.vtparser import VTParser, build_transitions

transitions = build_transitions()

# pprint(transitions)

parser = VTParser()

nethack = Path(__file__).parent / "nethack.txt"
chars = nethack.read_text().encode("utf-8")

print(repr(chars))

acc = []


def handler(parser, action, char):
    print(parser, action, char)


for char in chars:
    # print(f"{type(char)=}")
    print(f"{char=} {chr(char)=!r}")
    parser.advance(char, handler)
