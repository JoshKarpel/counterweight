from collections import defaultdict
from collections.abc import Mapping
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


def expand(d: dict[range | int | Literal["on_entry", "on_exit"], T]) -> dict[int, T]:
    expanded = {}
    for k, v in d.items():
        if isinstance(k, range):  # inclusive ranges!
            for kk in range(k.start, k.stop + 1):
                expanded[kk] = v
        else:
            expanded[k] = v

    return expanded


def build_transitions() -> Mapping[State, Mapping[int, tuple[Action | State, ...]]]:
    transitions = defaultdict(dict)

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
                0x9C: (State.GROUND,),
                0x1B: (State.ESCAPE,),
                0x98: (State.SOS_PM_APC_STRING,),
                0x9E: (State.SOS_PM_APC_STRING,),
                0x9F: (State.SOS_PM_APC_STRING,),
                0x90: (State.DCS_ENTRY,),
                0x9D: (State.OSC_STRING,),
                0x9B: (State.CSI_ENTRY,),
            }
        )

    transitions[State.GROUND].update(
        {
            range(0x00, 0x17): (Action.EXECUTE,),
            0x19: (Action.EXECUTE,),
            range(0x1C, 0x1F): (Action.EXECUTE,),
            range(0x20, 0x7F): (Action.PRINT,),
        }
    )

    transitions[State.ESCAPE].update(
        {
            "on_entry": (Action.CLEAR,),
            range(0x00, 0x17): (Action.EXECUTE,),
            0x19: (Action.EXECUTE,),
            range(0x1C, 0x1F): (Action.EXECUTE,),
            0x7F: (Action.IGNORE,),
            range(0x20, 0x2F): (Action.COLLECT, State.ESCAPE_INTERMEDIATE),
            range(0x30, 0x4F): (Action.ESC_DISPATCH, State.GROUND),
            range(0x51, 0x57): (Action.ESC_DISPATCH, State.GROUND),
            0x59: (Action.ESC_DISPATCH, State.GROUND),
            0x5A: (Action.ESC_DISPATCH, State.GROUND),
            0x5C: (Action.ESC_DISPATCH, State.GROUND),
            range(0x60, 0x7E): (Action.ESC_DISPATCH, State.GROUND),
            0x5B: (State.CSI_ENTRY,),
            0x5D: (State.OSC_STRING,),
            0x50: (State.DCS_ENTRY,),
            0x58: (State.SOS_PM_APC_STRING,),
            0x5E: (State.SOS_PM_APC_STRING,),
            0x5F: (State.SOS_PM_APC_STRING,),
        }
    )

    transitions[State.ESCAPE_INTERMEDIATE].update(
        {
            range(0x00, 0x17): (Action.EXECUTE,),
            0x19: (Action.EXECUTE,),
            range(0x1C, 0x1F): (Action.EXECUTE,),
            range(0x20, 0x2F): (Action.COLLECT,),
            0x7F: (Action.IGNORE,),
            range(0x30, 0x7E): (Action.ESC_DISPATCH, State.GROUND),
        }
    )

    transitions[State.CSI_ENTRY].update(
        {
            "on_entry": (Action.CLEAR,),
            range(0x00, 0x17): (Action.EXECUTE,),
            0x19: (Action.EXECUTE,),
            range(0x1C, 0x1F): (Action.EXECUTE,),
            0x7F: (Action.IGNORE,),
            range(0x20, 0x2F): (Action.COLLECT, State.CSI_INTERMEDIATE),
            0x3A: (State.CSI_IGNORE,),
            range(0x30, 0x39): (Action.PARAM, State.CSI_PARAM),
            0x3B: (Action.PARAM, State.CSI_PARAM),
            range(0x3C, 0x3F): (Action.COLLECT, State.CSI_PARAM),
            range(0x40, 0x7E): (Action.CSI_DISPATCH, State.GROUND),
        }
    )

    transitions[State.CSI_IGNORE].update(
        {
            range(0x00, 0x17): (Action.EXECUTE,),
            0x19: (Action.EXECUTE,),
            range(0x1C, 0x1F): (Action.EXECUTE,),
            range(0x20, 0x3F): (Action.IGNORE,),
            0x7F: (Action.IGNORE,),
            range(0x40, 0x7E): (State.GROUND,),
        }
    )

    transitions[State.CSI_PARAM].update(
        {
            range(0x00, 0x17): (Action.EXECUTE,),
            0x19: (Action.EXECUTE,),
            range(0x1C, 0x1F): (Action.EXECUTE,),
            range(0x30, 0x39): (Action.PARAM,),
            0x3B: (Action.PARAM,),
            0x7F: (Action.IGNORE,),
            0x3A: (State.CSI_IGNORE,),
            range(0x3C, 0x3F): (State.CSI_IGNORE,),
            range(0x20, 0x2F): (Action.COLLECT, State.CSI_INTERMEDIATE),
            range(0x40, 0x7E): (Action.CSI_DISPATCH, State.GROUND),
        }
    )

    transitions[State.CSI_INTERMEDIATE].update(
        {
            range(0x00, 0x17): (Action.EXECUTE,),
            0x19: (Action.EXECUTE,),
            range(0x1C, 0x1F): (Action.EXECUTE,),
            range(0x20, 0x2F): (Action.COLLECT,),
            0x7F: (Action.IGNORE,),
            range(0x30, 0x3F): (State.CSI_IGNORE,),
            range(0x40, 0x7E): (Action.CSI_DISPATCH, State.GROUND),
        }
    )

    transitions[State.DCS_ENTRY].update(
        {
            "on_entry": (Action.CLEAR,),
            range(0x00, 0x17): (Action.IGNORE,),
            0x19: (Action.IGNORE,),
            range(0x1C, 0x1F): (Action.IGNORE,),
            0x7F: (Action.IGNORE,),
            0x3A: (State.DCS_IGNORE,),
            range(0x20, 0x2F): (Action.COLLECT, State.DCS_INTERMEDIATE),
            range(0x30, 0x39): (Action.PARAM, State.DCS_PARAM),
            0x3B: (Action.PARAM, State.DCS_PARAM),
            range(0x3C, 0x3F): (Action.COLLECT, State.DCS_PARAM),
            range(0x40, 0x7E): (State.DCS_PASSTHROUGH,),
        }
    )

    transitions[State.DCS_INTERMEDIATE].update(
        {
            range(0x00, 0x17): (Action.IGNORE,),
            0x19: (Action.IGNORE,),
            range(0x1C, 0x1F): (Action.IGNORE,),
            range(0x20, 0x2F): (Action.COLLECT,),
            0x7F: (Action.IGNORE,),
            range(0x30, 0x3F): (State.DCS_IGNORE,),
            range(0x40, 0x7E): State.DCS_PASSTHROUGH,
        }
    )

    transitions[State.DCS_IGNORE].update(
        {
            range(0x00, 0x17): (Action.IGNORE,),
            0x19: (Action.IGNORE,),
            range(0x1C, 0x1F): (Action.IGNORE,),
            range(0x20, 0x7F): (Action.IGNORE,),
        }
    )

    transitions[State.DCS_PARAM].update(
        {
            range(0x00, 0x17): (Action.IGNORE,),
            0x19: (Action.IGNORE,),
            range(0x1C, 0x1F): (Action.IGNORE,),
            range(0x30, 0x39): (Action.PARAM,),
            0x3B: (Action.PARAM,),
            0x7F: (Action.IGNORE,),
            0x3A: (State.DCS_IGNORE,),
            range(0x3C, 0x3F): (State.DCS_IGNORE,),
            range(0x20, 0x2F): (Action.COLLECT, State.DCS_INTERMEDIATE),
            range(0x40, 0x7E): State.DCS_PASSTHROUGH,
        }
    )

    transitions[State.DCS_PASSTHROUGH].update(
        {
            "on_entry": (Action.HOOK,),
            range(0x00, 0x17): (Action.PUT,),
            0x19: (Action.PUT,),
            range(0x1C, 0x1F): (Action.PUT,),
            range(0x20, 0x7E): (Action.PUT,),
            0x7F: (Action.IGNORE,),
            "on_exit": (Action.UNHOOK,),
        }
    )

    transitions[State.SOS_PM_APC_STRING].update(
        {
            range(0x00, 0x17): (Action.IGNORE,),
            0x19: (Action.IGNORE,),
            range(0x1C, 0x1F): (Action.IGNORE,),
            range(0x20, 0x7F): (Action.IGNORE,),
        }
    )

    transitions[State.OSC_STRING].update(
        {
            "on_entry": (Action.OSC_START,),
            range(0x00, 0x17): (Action.IGNORE,),
            0x19: (Action.IGNORE,),
            range(0x1C, 0x1F): (Action.IGNORE,),
            range(0x20, 0x7F): (Action.OSC_PUT,),
            "on_exit": (Action.OSC_END,),
        }
    )

    return {k: expand(v) for k, v in transitions.items()}


TRANSITIONS = build_transitions()


class Parser:
    def __init__(self):
        self.state = State.GROUND
        self.intermediate_chars = []
        self.params = []
