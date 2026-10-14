from signal import SIG_DFL
from signal import SIGWINCH
from signal import getsignal
from signal import raise_signal

from counterweight.app import start_handling_resize_signal
from counterweight.app import stop_handling_resize_signal
from counterweight.events import AnyEvent
from counterweight.events import TerminalResized


def test_resize_signal_puts_a_terminal_resized_event_until_handling_stops() -> None:
    events: list[AnyEvent] = []

    start_handling_resize_signal(put_event=events.append)
    try:
        raise_signal(SIGWINCH)
    finally:
        stop_handling_resize_signal()

    assert events == [TerminalResized()]
    assert getsignal(SIGWINCH) == SIG_DFL
