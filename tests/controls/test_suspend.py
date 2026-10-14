import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from counterweight.controls import Suspend

TIMEOUT = 5


def test_suspending_to_the_shell_stops_the_whole_process_group() -> None:
    # The app and what started it, such as `uv run`, in a process group of their own, so the test doesn't stop itself.
    # Not a session of their own: Linux discards a stop signal sent to a group with no parent outside it in its session.
    with (
        subprocess.Popen(
            [sys.executable, "-c", "from counterweight.controls import Suspend; input(); Suspend.to_shell().handler()"],
            process_group=0,
            stdin=subprocess.PIPE,
            text=True,
        ) as app,
        subprocess.Popen([sys.executable, "-c", "input()"], process_group=app.pid, stdin=subprocess.PIPE) as starter,
        # Waiting on threads, so a process that never stops fails the test once the wait times out rather than hanging it,
        # and the kill ends the wait.
        ThreadPoolExecutor() as executor,
    ):
        try:
            waits = [executor.submit(os.waitpid, process.pid, os.WUNTRACED) for process in (app, starter)]
            assert app.stdin is not None
            app.stdin.write("\n")
            app.stdin.flush()
            statuses = [wait.result(timeout=TIMEOUT)[1] for wait in waits]
        finally:
            os.killpg(app.pid, signal.SIGKILL)

    assert [os.WIFSTOPPED(status) and os.WSTOPSIG(status) for status in statuses] == [signal.SIGTSTP] * 2


def test_suspending_to_the_shell_is_one_value() -> None:
    assert Suspend.to_shell() == Suspend.to_shell()
