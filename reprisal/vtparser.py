from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, TypeVar

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


@dataclass(frozen=True)
class Parser:
    state: State = State.GROUND
    intermediate_chars: list[int] = field(default_factory=list)
    params: list[int] = field(default_factory=list)

    def do_action(self, action: Action, char: int) -> None:
        match action:
            case Action.IGNORE:
                pass

            case Action.COLLECT:
                self.intermediate_chars.append(char)

            case Action.PARAM:
                if char == ord(";"):
                    self.params.append(0)
                else:
                    if not self.params:
                        self.params.append(0)
                    self.params[-1] = (self.params[-1] * 10) + (char - ord("0"))

            case Action.CLEAR:
                self.params.clear()
                self.intermediate_chars.clear()

            case _:
                pass  # ?!?!?

    def do_state_change(self, change: Change, char: int) -> None:
        action, new_state = change

        if new_state:
            exit_action, _ = TRANSITIONS[self.state].get("on_exit", (None, None))
            entry_action, _ = TRANSITIONS.get(new_state, {}).get("on_entry", (None, None))

            if exit_action is not None:
                self.do_action(action=exit_action, char=0)

            if action:
                self.do_action(action=action, char=char)

            if entry_action:
                self.do_action(action=entry_action, char=0)
        elif action:
            self.do_action(action=action, char=char)
