from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, TypeVar

from structlog import get_logger

logger = get_logger()


# Based on https://github.com/haberman/vtparse/blob/198ea4382f824dbb3f0e5b5553a9eb3290764694


class State(str, Enum):
    GROUND = "ground"

    ESCAPE = "escape"
    ESCAPE_INTERMEDIATE = "escape-intermediate"

    CSI_ENTRY = "csi-entry"
    CSI_IGNORE = "csi-ignore"
    CSI_PARAM = "csi-param"
    CSI_INTERMEDIATE = "cis-intermediate"

    DCS_ENTRY = "dcs-entry"
    DCS_IGNORE = "dcs-ignore"
    DCS_PARAM = "dcs-param"
    DCS_INTERMEDIATE = "dcs-intermediate"
    DCS_PASSTHROUGH = "dcs-passthrough"

    OSC_STRING = "osc-string"

    SOS_PM_APC_STRING = "sos-pm-apc-string"

    def __repr__(self) -> str:
        return str(self)


class Action(str, Enum):
    EXECUTE = "execute"
    IGNORE = "ignore"
    PRINT = "print"
    CLEAR = "clear"
    COLLECT = "collect"
    PARAM = "param"
    HOOK = "hook"
    UNHOOK = "unhook"
    PUT = "put"
    ESC_DISPATCH = "esc-dispatch"
    CSI_DISPATCH = "csi-dispatch"
    OSC_START = "osc-start"
    OSC_END = "osc-end"
    OSC_PUT = "osc-put"

    def __repr__(self) -> str:
        return str(self)


T = TypeVar("T")


Key = int | Literal["on_entry", "on_exit"]
Change = tuple[Action | None, State | None]


def expand(d: dict[range | Key, T]) -> dict[Key, T]:
    expanded: dict[Key, T] = {}
    for k, v in d.items():
        if isinstance(k, range):
            for kk in range(k.start, k.stop + 1):  # inclusive ranges!
                expanded[kk] = v
        else:
            expanded[k] = v

    return expanded


def build_transitions() -> Mapping[State, Mapping[Key, Change]]:
    transitions: dict[State, dict[range | Key, Change]] = defaultdict(dict)

    # anywhere transitions
    for state in State:
        transitions[state].update(
            {
                0x18: (Action.EXECUTE, State.GROUND),
                0x1A: (Action.EXECUTE, State.GROUND),
                range(0x80, 0x8F): (Action.EXECUTE, State.GROUND),
                range(0x91, 0x97): (Action.EXECUTE, State.GROUND),
                0x99: (Action.EXECUTE, State.GROUND),
                0x9A: (Action.EXECUTE, State.GROUND),
                0x9C: (None, State.GROUND),
                0x1B: (None, State.ESCAPE),
                0x98: (None, State.SOS_PM_APC_STRING),
                0x9E: (None, State.SOS_PM_APC_STRING),
                0x9F: (None, State.SOS_PM_APC_STRING),
                0x90: (None, State.DCS_ENTRY),
                0x9D: (None, State.OSC_STRING),
                0x9B: (None, State.CSI_ENTRY),
            }
        )

    transitions[State.GROUND].update(
        {
            range(0x00, 0x17): (Action.EXECUTE, None),
            0x19: (Action.EXECUTE, None),
            range(0x1C, 0x1F): (Action.EXECUTE, None),
            range(0x20, 0x7F): (Action.PRINT, None),
        }
    )

    transitions[State.ESCAPE].update(
        {
            "on_entry": (Action.CLEAR, None),
            range(0x00, 0x17): (Action.EXECUTE, None),
            0x19: (Action.EXECUTE, None),
            range(0x1C, 0x1F): (Action.EXECUTE, None),
            0x7F: (Action.IGNORE, None),
            range(0x20, 0x2F): (Action.COLLECT, State.ESCAPE_INTERMEDIATE),
            range(0x30, 0x4F): (Action.ESC_DISPATCH, State.GROUND),
            # TODO: below lets f1-f4 work on windows through wsl through windows terminal
            # range(0x30, 0x4E): (Action.ESC_DISPATCH, State.GROUND),
            # 0x4F: (Action.COLLECT, State.ESCAPE_INTERMEDIATE),
            range(0x51, 0x57): (Action.ESC_DISPATCH, State.GROUND),
            0x59: (Action.ESC_DISPATCH, State.GROUND),
            0x5A: (Action.ESC_DISPATCH, State.GROUND),
            0x5C: (Action.ESC_DISPATCH, State.GROUND),
            range(0x60, 0x7E): (Action.ESC_DISPATCH, State.GROUND),
            0x5B: (None, State.CSI_ENTRY),
            0x5D: (None, State.OSC_STRING),
            0x50: (None, State.DCS_ENTRY),
            0x58: (None, State.SOS_PM_APC_STRING),
            0x5E: (None, State.SOS_PM_APC_STRING),
            0x5F: (None, State.SOS_PM_APC_STRING),
        }
    )

    transitions[State.ESCAPE_INTERMEDIATE].update(
        {
            range(0x00, 0x17): (Action.EXECUTE, None),
            0x19: (Action.EXECUTE, None),
            range(0x1C, 0x1F): (Action.EXECUTE, None),
            range(0x20, 0x2F): (Action.COLLECT, None),
            0x7F: (Action.IGNORE, None),
            range(0x30, 0x7E): (Action.ESC_DISPATCH, State.GROUND),
        }
    )

    transitions[State.CSI_ENTRY].update(
        {
            "on_entry": (Action.CLEAR, None),
            range(0x00, 0x17): (Action.EXECUTE, None),
            0x19: (Action.EXECUTE, None),
            range(0x1C, 0x1F): (Action.EXECUTE, None),
            0x7F: (Action.IGNORE, None),
            range(0x20, 0x2F): (Action.COLLECT, State.CSI_INTERMEDIATE),
            0x3A: (None, State.CSI_IGNORE),
            range(0x30, 0x39): (Action.PARAM, State.CSI_PARAM),
            0x3B: (Action.PARAM, State.CSI_PARAM),
            range(0x3C, 0x3F): (Action.COLLECT, State.CSI_PARAM),
            range(0x40, 0x7E): (Action.CSI_DISPATCH, State.GROUND),
        }
    )

    transitions[State.CSI_IGNORE].update(
        {
            range(0x00, 0x17): (Action.EXECUTE, None),
            0x19: (Action.EXECUTE, None),
            range(0x1C, 0x1F): (Action.EXECUTE, None),
            range(0x20, 0x3F): (Action.IGNORE, None),
            0x7F: (Action.IGNORE, None),
            range(0x40, 0x7E): (None, State.GROUND),
        }
    )

    transitions[State.CSI_PARAM].update(
        {
            range(0x00, 0x17): (Action.EXECUTE, None),
            0x19: (Action.EXECUTE, None),
            range(0x1C, 0x1F): (Action.EXECUTE, None),
            range(0x30, 0x39): (Action.PARAM, None),
            0x3B: (Action.PARAM, None),
            0x7F: (Action.IGNORE, None),
            0x3A: (None, State.CSI_IGNORE),
            range(0x3C, 0x3F): (None, State.CSI_IGNORE),
            range(0x20, 0x2F): (Action.COLLECT, State.CSI_INTERMEDIATE),
            range(0x40, 0x7E): (Action.CSI_DISPATCH, State.GROUND),
        }
    )

    transitions[State.CSI_INTERMEDIATE].update(
        {
            range(0x00, 0x17): (Action.EXECUTE, None),
            0x19: (Action.EXECUTE, None),
            range(0x1C, 0x1F): (Action.EXECUTE, None),
            range(0x20, 0x2F): (Action.COLLECT, None),
            0x7F: (Action.IGNORE, None),
            range(0x30, 0x3F): (None, State.CSI_IGNORE),
            range(0x40, 0x7E): (Action.CSI_DISPATCH, State.GROUND),
        }
    )

    transitions[State.DCS_ENTRY].update(
        {
            "on_entry": (Action.CLEAR, None),
            range(0x00, 0x17): (Action.IGNORE, None),
            0x19: (Action.IGNORE, None),
            range(0x1C, 0x1F): (Action.IGNORE, None),
            0x7F: (Action.IGNORE, None),
            0x3A: (None, State.DCS_IGNORE),
            range(0x20, 0x2F): (Action.COLLECT, State.DCS_INTERMEDIATE),
            range(0x30, 0x39): (Action.PARAM, State.DCS_PARAM),
            0x3B: (Action.PARAM, State.DCS_PARAM),
            range(0x3C, 0x3F): (Action.COLLECT, State.DCS_PARAM),
            range(0x40, 0x7E): (None, State.DCS_PASSTHROUGH),
        }
    )

    transitions[State.DCS_INTERMEDIATE].update(
        {
            range(0x00, 0x17): (Action.IGNORE, None),
            0x19: (Action.IGNORE, None),
            range(0x1C, 0x1F): (Action.IGNORE, None),
            range(0x20, 0x2F): (Action.COLLECT, None),
            0x7F: (Action.IGNORE, None),
            range(0x30, 0x3F): (None, State.DCS_IGNORE),
            range(0x40, 0x7E): (None, State.DCS_PASSTHROUGH),
        }
    )

    transitions[State.DCS_IGNORE].update(
        {
            range(0x00, 0x17): (Action.IGNORE, None),
            0x19: (Action.IGNORE, None),
            range(0x1C, 0x1F): (Action.IGNORE, None),
            range(0x20, 0x7F): (Action.IGNORE, None),
        }
    )

    transitions[State.DCS_PARAM].update(
        {
            range(0x00, 0x17): (Action.IGNORE, None),
            0x19: (Action.IGNORE, None),
            range(0x1C, 0x1F): (Action.IGNORE, None),
            range(0x30, 0x39): (Action.PARAM, None),
            0x3B: (Action.PARAM, None),
            0x7F: (Action.IGNORE, None),
            0x3A: (None, State.DCS_IGNORE),
            range(0x3C, 0x3F): (None, State.DCS_IGNORE),
            range(0x20, 0x2F): (Action.COLLECT, State.DCS_INTERMEDIATE),
            range(0x40, 0x7E): (None, State.DCS_PASSTHROUGH),
        }
    )

    transitions[State.DCS_PASSTHROUGH].update(
        {
            "on_entry": (Action.HOOK, None),
            range(0x00, 0x17): (Action.PUT, None),
            0x19: (Action.PUT, None),
            range(0x1C, 0x1F): (Action.PUT, None),
            range(0x20, 0x7E): (Action.PUT, None),
            0x7F: (Action.IGNORE, None),
            "on_exit": (Action.UNHOOK, None),
        }
    )

    transitions[State.SOS_PM_APC_STRING].update(
        {
            range(0x00, 0x17): (Action.IGNORE, None),
            0x19: (Action.IGNORE, None),
            range(0x1C, 0x1F): (Action.IGNORE, None),
            range(0x20, 0x7F): (Action.IGNORE, None),
        }
    )

    transitions[State.OSC_STRING].update(
        {
            "on_entry": (Action.OSC_START, None),
            range(0x00, 0x17): (Action.IGNORE, None),
            0x19: (Action.IGNORE, None),
            range(0x1C, 0x1F): (Action.IGNORE, None),
            range(0x20, 0x7F): (Action.OSC_PUT, None),
            "on_exit": (Action.OSC_END, None),
        }
    )

    return {k: expand(v) for k, v in transitions.items()}


TRANSITIONS = build_transitions()

Handler = Callable[[Action, tuple[int, ...], tuple[int, ...], int], None]


@dataclass
class VTParser:
    state: State = State.GROUND
    intermediate_chars: list[int] = field(default_factory=list)
    params: list[int] = field(default_factory=list)

    def do_action(self, action: Action, char: int, handler: Handler) -> None:
        match action:
            case Action.IGNORE:
                pass

            case Action.COLLECT:
                self.intermediate_chars.append(char)

            case Action.PARAM:
                if char == ord(";"):
                    self.params.append(0)
                else:
                    self.params.append(char - ord("0"))

            case Action.CLEAR:
                self.params.clear()
                self.intermediate_chars.clear()

            case _:
                handler(action, tuple(self.intermediate_chars), tuple(self.params), char)

    def do_state_change(self, change: Change, char: int, handler: Callable[[VTParser, Action, int], None]) -> None:
        action, new_state = change

        if new_state:
            exit_action, _ = TRANSITIONS[self.state].get("on_exit", (None, None))
            entry_action, _ = TRANSITIONS.get(new_state, {}).get("on_entry", (None, None))

            logger.debug(f"{char=} {chr(char)=!r} {hex(char)=} {action=} {new_state=} {exit_action=} {entry_action=}")
            if exit_action is not None:
                self.do_action(action=exit_action, char=0, handler=handler)

            if action:
                self.do_action(action=action, char=char, handler=handler)

            if entry_action:
                self.do_action(action=entry_action, char=0, handler=handler)

            self.state = new_state
        elif action:
            logger.debug(f"{char=} {chr(char)=!r} {hex(char)=} {action=} {new_state=}")
            self.do_action(action=action, char=char, handler=handler)

    def advance(self, char: int, handler: Callable[[VTParser, Action, int], None]) -> None:
        change = TRANSITIONS[self.state][char]
        self.do_state_change(change=change, char=char, handler=handler)


# From https://github.com/Textualize/textual/blob/c966243b059f0352e2a23b9695776838195364a3/src/textual/keys.py


class Keys(str, Enum):  # type: ignore[no-redef]
    Escape = "escape"  # Also Control-[
    ShiftEscape = "shift+escape"
    Return = "return"

    ControlAt = "ctrl+@"  # Also Control-Space.

    ControlA = "ctrl+a"
    ControlB = "ctrl+b"
    ControlC = "ctrl+c"
    ControlD = "ctrl+d"
    ControlE = "ctrl+e"
    ControlF = "ctrl+f"
    ControlG = "ctrl+g"
    ControlH = "ctrl+h"
    ControlI = "ctrl+i"  # Tab
    ControlJ = "ctrl+j"  # Newline
    ControlK = "ctrl+k"
    ControlL = "ctrl+l"
    ControlM = "ctrl+m"  # Carriage return
    ControlN = "ctrl+n"
    ControlO = "ctrl+o"
    ControlP = "ctrl+p"
    ControlQ = "ctrl+q"
    ControlR = "ctrl+r"
    ControlS = "ctrl+s"
    ControlT = "ctrl+t"
    ControlU = "ctrl+u"
    ControlV = "ctrl+v"
    ControlW = "ctrl+w"
    ControlX = "ctrl+x"
    ControlY = "ctrl+y"
    ControlZ = "ctrl+z"

    Control1 = "ctrl+1"
    Control2 = "ctrl+2"
    Control3 = "ctrl+3"
    Control4 = "ctrl+4"
    Control5 = "ctrl+5"
    Control6 = "ctrl+6"
    Control7 = "ctrl+7"
    Control8 = "ctrl+8"
    Control9 = "ctrl+9"
    Control0 = "ctrl+0"

    ControlShift1 = "ctrl+shift+1"
    ControlShift2 = "ctrl+shift+2"
    ControlShift3 = "ctrl+shift+3"
    ControlShift4 = "ctrl+shift+4"
    ControlShift5 = "ctrl+shift+5"
    ControlShift6 = "ctrl+shift+6"
    ControlShift7 = "ctrl+shift+7"
    ControlShift8 = "ctrl+shift+8"
    ControlShift9 = "ctrl+shift+9"
    ControlShift0 = "ctrl+shift+0"

    ControlBackslash = "ctrl+backslash"
    ControlSquareClose = "ctrl+right_square_bracket"
    ControlCircumflex = "ctrl+circumflex_accent"
    ControlUnderscore = "ctrl+underscore"

    Left = "left"
    Right = "right"
    Up = "up"
    Down = "down"
    Home = "home"
    End = "end"
    Insert = "insert"
    Delete = "delete"
    PageUp = "pageup"
    PageDown = "pagedown"

    ControlLeft = "ctrl+left"
    ControlRight = "ctrl+right"
    ControlUp = "ctrl+up"
    ControlDown = "ctrl+down"
    ControlHome = "ctrl+home"
    ControlEnd = "ctrl+end"
    ControlInsert = "ctrl+insert"
    ControlDelete = "ctrl+delete"
    ControlPageUp = "ctrl+pageup"
    ControlPageDown = "ctrl+pagedown"

    ShiftLeft = "shift+left"
    ShiftRight = "shift+right"
    ShiftUp = "shift+up"
    ShiftDown = "shift+down"
    ShiftHome = "shift+home"
    ShiftEnd = "shift+end"
    ShiftInsert = "shift+insert"
    ShiftDelete = "shift+delete"
    ShiftPageUp = "shift+pageup"
    ShiftPageDown = "shift+pagedown"

    ControlShiftLeft = "ctrl+shift+left"
    ControlShiftRight = "ctrl+shift+right"
    ControlShiftUp = "ctrl+shift+up"
    ControlShiftDown = "ctrl+shift+down"
    ControlShiftHome = "ctrl+shift+home"
    ControlShiftEnd = "ctrl+shift+end"
    ControlShiftInsert = "ctrl+shift+insert"
    ControlShiftDelete = "ctrl+shift+delete"
    ControlShiftPageUp = "ctrl+shift+pageup"
    ControlShiftPageDown = "ctrl+shift+pagedown"

    BackTab = "shift+tab"  # shift + tab

    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"
    F13 = "f13"
    F14 = "f14"
    F15 = "f15"
    F16 = "f16"
    F17 = "f17"
    F18 = "f18"
    F19 = "f19"
    F20 = "f20"
    F21 = "f21"
    F22 = "f22"
    F23 = "f23"
    F24 = "f24"

    ControlF1 = "ctrl+f1"
    ControlF2 = "ctrl+f2"
    ControlF3 = "ctrl+f3"
    ControlF4 = "ctrl+f4"
    ControlF5 = "ctrl+f5"
    ControlF6 = "ctrl+f6"
    ControlF7 = "ctrl+f7"
    ControlF8 = "ctrl+f8"
    ControlF9 = "ctrl+f9"
    ControlF10 = "ctrl+f10"
    ControlF11 = "ctrl+f11"
    ControlF12 = "ctrl+f12"
    ControlF13 = "ctrl+f13"
    ControlF14 = "ctrl+f14"
    ControlF15 = "ctrl+f15"
    ControlF16 = "ctrl+f16"
    ControlF17 = "ctrl+f17"
    ControlF18 = "ctrl+f18"
    ControlF19 = "ctrl+f19"
    ControlF20 = "ctrl+f20"
    ControlF21 = "ctrl+f21"
    ControlF22 = "ctrl+f22"
    ControlF23 = "ctrl+f23"
    ControlF24 = "ctrl+f24"

    # Matches any key.
    Any = "<any>"

    # Special.
    ScrollUp = "<scroll-up>"
    ScrollDown = "<scroll-down>"

    # For internal use: key which is ignored.
    # (The key binding for this key should not do anything.)
    Ignore = "<ignore>"

    # Some 'Key' aliases (for backwardshift+compatibility).
    ControlSpace = "ctrl-at"
    Tab = "tab"
    Space = "space"
    Enter = "enter"
    Backspace = "backspace"

    def __repr__(self) -> str:
        return str(self)


# Adapated from https://github.com/Textualize/textual/blob/c966243b059f0352e2a23b9695776838195364a3/src/textual/_ansi_sequences.py

PRINT = {
    0x0A: (Keys.Enter,),
    0x20: (Keys.Space,),
    0x7F: (Keys.Backspace,),
}

EXECUTE_LOOKUP = {
    0x00: (Keys.ControlSpace,),
    0x01: (Keys.ControlA,),
    0x02: (Keys.ControlB,),
    0x03: (Keys.ControlC,),
    0x04: (Keys.ControlD,),
    0x05: (Keys.ControlE,),
    0x06: (Keys.ControlF,),
    0x07: (Keys.ControlG,),
    0x08: (Keys.Backspace,),
    0x09: (Keys.Tab,),
    0x0A: (Keys.Enter,),
    0x0B: (Keys.ControlK,),
    0x0C: (Keys.ControlL,),
    0x0E: (Keys.ControlN,),
    0x0F: (Keys.ControlO,),
    0x10: (Keys.ControlP,),
    0x11: (Keys.ControlQ,),
    0x12: (Keys.ControlR,),
    0x13: (Keys.ControlS,),
    0x14: (Keys.ControlT,),
    0x15: (Keys.ControlU,),
    0x16: (Keys.ControlV,),
    0x17: (Keys.ControlW,),
    0x18: (Keys.ControlX,),
    0x19: (Keys.ControlY,),
    0x1A: (Keys.ControlZ,),
}

CSI_LOOKUP = {
    ((), 0x41): (Keys.Up,),
    ((), 0x42): (Keys.Down,),
    ((), 0x43): (Keys.Left,),
    ((), 0x44): (Keys.Right,),
    ((1, 1), 0x7E): (Keys.F1,),
    ((1, 2), 0x7E): (Keys.F2,),
    ((1, 3), 0x7E): (Keys.F3,),
    ((1, 4), 0x7E): (Keys.F4,),
    ((1, 5), 0x7E): (Keys.F5,),
    ((1, 7), 0x7E): (Keys.F6,),
    ((1, 8), 0x7E): (Keys.F7,),
    ((1, 9), 0x7E): (Keys.F8,),
    ((2, 0), 0x7E): (Keys.F9,),
    ((2, 1), 0x7E): (Keys.F10,),
    ((2, 3), 0x7E): (Keys.F11,),
    ((2, 4), 0x7E): (Keys.F12,),
    ((2, 5), 0x7E): (Keys.F13,),
    ((2, 6), 0x7E): (Keys.F14,),
    ((2, 8), 0x7E): (Keys.F15,),
    ((2, 9), 0x7E): (Keys.F16,),
    ((3, 1), 0x7E): (Keys.F17,),
    ((3, 2), 0x7E): (Keys.F18,),
    ((3, 3), 0x7E): (Keys.F19,),
    ((3, 4), 0x7E): (Keys.F20,),
}

ESC_LOOKUP = {
    # See comment in transition table, these are not reachable right now
    # ((0x4F,), 0x50): (Keys.F1,),
    # ((0x4F,), 0x51): (Keys.F2,),
    # ((0x4F,), 0x52): (Keys.F3,),
    # ((0x4F,), 0x53): (Keys.F4,),
}
