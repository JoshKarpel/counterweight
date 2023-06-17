from reprisal.vtparser import TRANSITIONS, State


def test_transition_table_is_complete() -> None:
    for state in State:
        for char in range(0x00, 0xA0):
            assert char in TRANSITIONS[state]
