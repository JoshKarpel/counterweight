import io
from datetime import timedelta
from pathlib import Path
from types import ModuleType

import pytest

from benchmarks import agent
from benchmarks import agent_markdown
from benchmarks import agent_typing
from benchmarks import canvas
from benchmarks import chat
from benchmarks import dashboard
from benchmarks import picker
from benchmarks import tasks
from benchmarks import top
from benchmarks.harness import autopilot
from benchmarks.harness import run
from benchmarks.parsing import INPUTS
from benchmarks.parsing import InputTiming
from benchmarks.parsing import ParsingTimings
from benchmarks.parsing import parsing_table
from benchmarks.parsing import time_parsing
from benchmarks.snapshots import SCENARIOS
from benchmarks.snapshots import Scenario
from benchmarks.snapshots import SnapshotTimings
from benchmarks.snapshots import snapshots_table
from benchmarks.snapshots import time_snapshots
from benchmarks.stacks import EVENT_LOOP
from benchmarks.stacks import LOOP_ITSELF
from benchmarks.stacks import STARTUP
from benchmarks.stacks import Frame
from benchmarks.stacks import parse_collapsed
from benchmarks.stacks import parse_frame
from benchmarks.stacks import summarize
from benchmarks.tables import Column
from benchmarks.tables import render_table
from benchmarks.workloads import WORKLOADS
from counterweight import _output as output
from counterweight import app
from counterweight._input_parsing import parse_input
from counterweight.controls import Bell
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.events import KeyPressed


@pytest.mark.parametrize("name", WORKLOADS)
async def test_workload_renders_every_frame(name: str, tmp_path: Path) -> None:
    timings = await run(WORKLOADS[name], frames=5, warmup=1, snapshot=tmp_path / "snapshot.txt")

    assert len(timings.frame_ms) == 3
    assert (tmp_path / "snapshot.txt").read_text().strip()


@pytest.mark.parametrize(
    ("name", "twin"),
    [
        ("canvas-element", "canvas"),
        ("dashboard-local", "dashboard"),
        ("dashboard-memo", "dashboard"),
        ("top-memo", "top"),
        ("agent-memo", "agent"),
        ("agent-markdown-memo", "agent-markdown"),
    ],
)
async def test_workload_draws_the_same_last_frame_as_its_twin(name: str, twin: str, tmp_path: Path) -> None:
    for workload in (name, twin):
        await run(WORKLOADS[workload], frames=7, warmup=1, snapshot=tmp_path / f"{workload}.txt", check_purity=True)

    assert (tmp_path / f"{name}.txt").read_text() == (tmp_path / f"{twin}.txt").read_text()


def test_autopilot_sends_each_frames_interjections_before_the_key_press_that_steps_to_it() -> None:
    bell = Bell()

    assert autopilot(3, None, {1: (bell,)}, (), "n") == [
        KeyPressed(key="n"),
        bell,
        KeyPressed(key="n"),
        KeyPressed(key="n"),
        Quit(),
    ]


def test_autopilot_sends_cycled_interjections_one_a_frame_after_that_frames_interjections() -> None:
    bell, typed_a, typed_b = Bell(), KeyPressed(key="a"), KeyPressed(key="b")
    step = KeyPressed(key="f12")

    assert autopilot(3, None, {1: (bell,)}, (typed_a, typed_b), "f12") == [
        typed_a,
        step,
        bell,
        typed_b,
        step,
        typed_a,
        step,
        Quit(),
    ]


async def test_typing_agent_types_into_its_prompt_while_its_transcript_streams(tmp_path: Path) -> None:
    timings = await run(WORKLOADS["agent-typing"], frames=10, warmup=0, snapshot=tmp_path / "snapshot.txt")

    *_, prompt, _ = (tmp_path / "snapshot.txt").read_text().splitlines()
    assert (len(timings.frame_ms), prompt.strip("│ ")) == (9, "Before you")


async def test_typing_agent_empties_its_prompt_when_it_sends_the_message(tmp_path: Path) -> None:
    frames = len(agent_typing.MESSAGE)
    await run(WORKLOADS["agent-typing"], frames=frames, warmup=0, snapshot=tmp_path / "snapshot.txt")

    *_, prompt, _ = (tmp_path / "snapshot.txt").read_text().splitlines()
    assert prompt.strip("│ ") == "Try fix the failing test or explain this diff"


async def test_picker_burst_replaces_the_last_frames_query_with_the_next_in_each_burst(tmp_path: Path) -> None:
    await run(WORKLOADS["picker-burst"], frames=5, warmup=0, snapshot=tmp_path / "snapshot.txt")

    field, *_ = (tmp_path / "snapshot.txt").read_text().splitlines()
    assert field.rstrip() == "> srcpai"


async def test_scrolled_agent_reads_back_where_its_twin_follows_the_end(tmp_path: Path) -> None:
    frames = agent.SCROLLED_BACK_AT + 5
    for workload in ("agent", "agent-scrolled"):
        await run(WORKLOADS[workload], frames=frames, warmup=1, snapshot=tmp_path / f"{workload}.txt")

    assert (tmp_path / "agent.txt").read_text() != (tmp_path / "agent-scrolled.txt").read_text()


async def test_agent_transcript_jumps_back_to_the_start_of_an_earlier_tool_call() -> None:
    frames: list[output.Frame] = []
    jump = KeyPressed(key="[")

    await app(
        agent.WORKLOAD.root([]),
        headless=True,
        dimensions=(80, 14),
        # The first jump is to the newest tool call, which is already in view at the end.
        autopilot=[*(KeyPressed(key="n") for _ in range(120)), jump, jump, Screenshot(handler=frames.append), Quit()],
        check_purity=True,
    )

    _, top, title, *_ = frames[0].text(ansi=False).split("\n")
    assert (top.strip()[0], title.strip()[:6]) == ("╭", "│Edit ")


@pytest.mark.parametrize("name", WORKLOADS)
async def test_live_workload_renders_until_quit(name: str) -> None:
    capture = io.StringIO()

    await app(
        WORKLOADS[name].live_root(timedelta(seconds=1)),
        headless=True,
        dimensions=WORKLOADS[name].dimensions,
        autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()],
        check_purity=True,
    )

    assert capture.getvalue().strip()


@pytest.mark.parametrize(
    "module", [agent, agent_markdown, canvas, chat, dashboard, picker, tasks, top], ids=lambda m: m.__name__
)
def test_workload_steps_to_the_same_models_every_run(module: ModuleType) -> None:
    def models() -> list[object]:
        model = module.initial()
        steps = [model]
        for _ in range(7):
            model = module.step(model)
            steps.append(model)
        return steps

    assert models() == models()


def test_parse_frame_splits_file_function_and_line() -> None:
    assert parse_frame("_layout.py:compute_layout:42") == Frame(file="_layout.py", function="compute_layout")


def test_parse_frame_keeps_artificial_frames_as_bare_functions() -> None:
    assert parse_frame("<GC>") == Frame(file="", function="<GC>")


COLLAPSED = """\
tid:7;<frozen runpy>:_run_module_as_main:201;__main__.py:<module>:9 3
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;_app.py:app:113;_app.py:render_loop:296;_layout.py:compute_layout:40;_layout.py:_measure_text:80 5
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;_app.py:app:113;_app.py:render_loop:296;_layout.py:compute_layout:41 2
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;_app.py:app:113;_app.py:render_loop:300;_paint.py:paint_layout:60;<GC> 7
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;_app.py:app:113;_app.py:render_loop:310 11
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;capture.py:run_sink:120;renderers.py:render:80 13
tid:7;base_events.py:BaseEventLoop._run_once:2001;selectors.py:EpollSelector.select:452 17
"""


def test_summary_attributes_samples_to_the_function_render_loop_called() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.stages == {
        STARTUP: 3,
        "_layout.py:compute_layout": 7,
        "_paint.py:paint_layout": 7,
        LOOP_ITSELF: 11,
        "task capture.py:run_sink": 13,
        EVENT_LOOP: 17,
    }
    assert (summary.total_samples, summary.running_samples) == (58, 55)


def test_summary_counts_self_samples_on_the_innermost_frame() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.self_samples == {
        "_layout.py:_measure_text": 5,
        "_layout.py:compute_layout": 2,
        "<GC>": 7,
        "_app.py:render_loop": 11,
        "renderers.py:render": 13,
        "selectors.py:EpollSelector.select": 17,
    }


def test_summary_counts_inclusive_samples_only_below_each_stage_root() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.inclusive_samples == {
        "_layout.py:compute_layout": 7,
        "_layout.py:_measure_text": 5,
        "_paint.py:paint_layout": 7,
        "<GC>": 7,
        "capture.py:run_sink": 13,
        "renderers.py:render": 13,
        "selectors.py:EpollSelector.select": 17,
    }


def test_summary_counts_the_benchmark_command_only_while_it_runs_the_workload() -> None:
    command = "tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;commands.py:action:679;__main__.py:run_workload"
    collapsed = f"""\
{command}:93;harness.py:run:174;_app.py:app:139 3
{command}:93;harness.py:run:174;_app.py:app:113;_app.py:render_loop:296;_layout.py:compute_layout:40 5
{command}:95;__main__.py:frames_table:182 7
"""

    summary = summarize(parse_collapsed(collapsed))

    assert summary.stages == {"task harness.py:run": 3, "_layout.py:compute_layout": 5, STARTUP: 7}


def test_table_pads_columns_to_their_widest_cell_and_right_aligns_on_request() -> None:
    table = render_table(
        (Column("Name"), Column("Time", is_right_aligned=True)), [("render", "1.5 ms"), ("go", "12.25 ms")]
    )

    assert table == "Name        Time\n──────  ────────\nrender    1.5 ms\ngo      12.25 ms\n"


def test_table_stacks_the_lines_of_a_multi_line_cell_within_its_row() -> None:
    table = render_table((Column("Workload"), Column("About")), [("top", "busy\nvery"), ("idle", "calm")], title="All")

    assert table == "All\nWorkload  About\n────────  ─────\ntop       busy\n          very\nidle      calm\n"


@pytest.mark.parametrize("name", INPUTS)
def test_parsing_input_is_whole_events_with_nothing_skipped_or_held_over(name: str) -> None:
    parsed = parse_input(INPUTS[name], is_final=False)

    assert parsed.events
    assert (parsed.skipped, parsed.end) == ((), len(INPUTS[name]))


def test_time_parsing_times_each_input_by_name() -> None:
    timings = time_parsing({"arrow": b"\x1b[A", "text": "日本".encode()}, repeat=1)

    assert {name: timing.size for name, timing in timings.inputs.items()} == {"arrow": 3, "text": 6}
    assert all(timing.read_us > 0 for timing in timings.inputs.values())


def test_parsing_timings_load_what_they_dump(tmp_path: Path) -> None:
    timings = ParsingTimings(source="src", inputs={"key": InputTiming(size=3, read_us=1.5)})
    timings.dump(tmp_path / "run.parsing.json")

    assert ParsingTimings.load(tmp_path / "run.parsing.json") == timings


def test_parsing_table_compares_only_the_inputs_both_runs_timed() -> None:
    before = ParsingTimings(
        source="a", inputs={"key": InputTiming(size=1, read_us=2.0), "paste": InputTiming(size=9, read_us=7.0)}
    )
    after = ParsingTimings(source="b", inputs={"key": InputTiming(size=1, read_us=1.5)})

    table = parsing_table({"before": before, "after": after})

    assert [row.split() for row in table.splitlines()[3:]] == [["key", "1", "2.00", "1.50", "-25%"]]


def test_time_snapshots_times_each_scenario_by_name() -> None:
    timings = time_snapshots({"line": Scenario(setup=b"a\r\n", step=b"b\r\n"), "none": SCENARIOS["unchanged"]}, 1, 2)

    assert list(timings.snapshot_us) == ["line", "none"]
    assert all(us > 0 for us in timings.snapshot_us.values())


def test_snapshot_timings_load_what_they_dump(tmp_path: Path) -> None:
    timings = SnapshotTimings(source="src", snapshot_us={"plain-line": 420.5})
    timings.dump(tmp_path / "run.snapshots.json")

    assert SnapshotTimings.load(tmp_path / "run.snapshots.json") == timings


def test_snapshots_table_compares_only_the_scenarios_both_runs_timed() -> None:
    before = SnapshotTimings(source="a", snapshot_us={"plain-line": 400.0, "wide-line": 900.0})
    after = SnapshotTimings(source="b", snapshot_us={"plain-line": 300.0})

    table = snapshots_table({"before": before, "after": after})

    assert [row.split() for row in table.splitlines()[3:]] == [["plain-line", "400.0", "300.0", "-25%"]]
