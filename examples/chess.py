import asyncio
from enum import Enum, StrEnum
from pathlib import Path
from typing import NamedTuple

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Screenshot
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = get_logger()


class Player(StrEnum):
    White = "white"
    Black = "black"


class WhiteBlack(NamedTuple):
    white: str
    black: str


class PieceCharacter(Enum):
    Pawn = WhiteBlack(white="♙", black="♙")
    Knight = WhiteBlack(white="♞", black="♞")
    Bishop = WhiteBlack(white="♝", black="♝")
    Rook = WhiteBlack(white="♜", black="♜")
    Queen = WhiteBlack(white="♛", black="♛")
    King = WhiteBlack(white="♚", black="♚")

    def char(self, player: Player) -> str:
        return self.value.white if player is Player.White else self.value.black


@component
def root() -> Div:
    def on_key(event: KeyPressed) -> AnyControl | None:
        if event.key == Key.Enter:
            return Screenshot.to_file(Path("chess.svg"))
        else:
            return None

    return Div(
        style=row | align_self_stretch | align_children_center,
        children=[board()],
        on_key=on_key,
    )


@component
def board() -> Div:
    positions, set_positions = use_state(
        {
            (0, 0): (Player.White, PieceCharacter.Rook),
            (0, 1): (Player.White, PieceCharacter.Knight),
            (0, 2): (Player.White, PieceCharacter.Bishop),
            (0, 3): (Player.White, PieceCharacter.Queen),
            (0, 4): (Player.White, PieceCharacter.King),
            (0, 5): (Player.White, PieceCharacter.Bishop),
            (0, 6): (Player.White, PieceCharacter.Knight),
            (0, 7): (Player.White, PieceCharacter.Rook),
            (1, 0): (Player.White, PieceCharacter.Pawn),
            (1, 1): (Player.White, PieceCharacter.Pawn),
            (1, 2): (Player.White, PieceCharacter.Pawn),
            (1, 3): (Player.White, PieceCharacter.Pawn),
            (1, 4): (Player.White, PieceCharacter.Pawn),
            (1, 5): (Player.White, PieceCharacter.Pawn),
            (1, 6): (Player.White, PieceCharacter.Pawn),
            (1, 7): (Player.White, PieceCharacter.Pawn),
            (7, 0): (Player.Black, PieceCharacter.Rook),
            (7, 1): (Player.Black, PieceCharacter.Knight),
            (7, 2): (Player.Black, PieceCharacter.Bishop),
            (7, 3): (Player.Black, PieceCharacter.Queen),
            (7, 4): (Player.Black, PieceCharacter.King),
            (7, 5): (Player.Black, PieceCharacter.Bishop),
            (7, 6): (Player.Black, PieceCharacter.Knight),
            (7, 7): (Player.Black, PieceCharacter.Rook),
            (6, 0): (Player.Black, PieceCharacter.Pawn),
            (6, 1): (Player.Black, PieceCharacter.Pawn),
            (6, 2): (Player.Black, PieceCharacter.Pawn),
            (6, 3): (Player.Black, PieceCharacter.Pawn),
            (6, 4): (Player.Black, PieceCharacter.Pawn),
            (6, 5): (Player.Black, PieceCharacter.Pawn),
            (6, 6): (Player.Black, PieceCharacter.Pawn),
            (6, 7): (Player.Black, PieceCharacter.Pawn),
        },
    )

    b = text_bg_amber_600
    w = text_bg_amber_900
    rows: list[list[Text]] = []
    for r in range(8):
        rows.append([])
        for c in range(8):
            player_piece = positions.get((r, c))
            s = b if (r + c) % 2 == 0 else w
            if not player_piece:
                rows[-1].append(
                    Text(
                        style=s,
                        content="  ",
                    )
                )
            else:
                player, piece = player_piece
                rows[-1].append(
                    Text(
                        style=s | (text_white if player is Player.White else text_black),
                        content=f" {piece.char(player)}",
                    )
                )

    return Div(
        style=col | justify_children_center | align_children_center,
        children=[
            Div(
                style=row | weight_none | justify_children_center | align_children_center,
                children=r,
            )
            for r in rows
        ],
    )


if __name__ == "__main__":
    asyncio.run(app(root))
