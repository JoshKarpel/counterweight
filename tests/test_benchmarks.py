from pathlib import Path
from types import ModuleType

import pytest

from benchmarks import agent, canvas, dashboard, top
from benchmarks.harness import run
from benchmarks.stacks import EVENT_LOOP, LOOP_ITSELF, STARTUP, Frame, parse_collapsed, parse_frame, summarize
from benchmarks.workloads import WORKLOADS


@pytest.mark.parametrize("name", WORKLOADS)
async def test_workload_renders_every_frame(name: str, tmp_path: Path) -> None:
    timings = await run(WORKLOADS[name], frames=5, warmup=1, snapshot=tmp_path / "snapshot.txt")

    assert len(timings.frame_ms) == 4
    assert (tmp_path / "snapshot.txt").read_text().strip()


@pytest.mark.parametrize("module", [agent, canvas, dashboard, top], ids=lambda m: m.__name__)
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
    assert parse_frame("layout.py:compute_layout:42") == Frame(file="layout.py", function="compute_layout")


def test_parse_frame_keeps_artificial_frames_as_bare_functions() -> None:
    assert parse_frame("<GC>") == Frame(file="", function="<GC>")


COLLAPSED = """\
tid:7;<frozen runpy>:_run_module_as_main:201;__main__.py:<module>:9 3
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;app.py:app:113;app.py:render_loop:296;layout.py:compute_layout:40;layout.py:_measure_text:80 5
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;app.py:app:113;app.py:render_loop:296;layout.py:compute_layout:41 2
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;app.py:app:113;app.py:render_loop:300;paint.py:paint_layout:60;<GC> 7
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;app.py:app:113;app.py:render_loop:310 11
tid:7;base_events.py:BaseEventLoop._run_once:2050;events.py:Handle._run:94;capture.py:run_sink:120;renderers.py:render:80 13
tid:7;base_events.py:BaseEventLoop._run_once:2001;selectors.py:EpollSelector.select:452 17
"""


def test_summary_attributes_samples_to_the_function_render_loop_called() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.stages == {
        STARTUP: 3,
        "layout.py:compute_layout": 7,
        "paint.py:paint_layout": 7,
        LOOP_ITSELF: 11,
        "task capture.py:run_sink": 13,
        EVENT_LOOP: 17,
    }
    assert (summary.total_samples, summary.running_samples) == (58, 55)


def test_summary_counts_self_samples_on_the_innermost_frame() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.self_samples == {
        "layout.py:_measure_text": 5,
        "layout.py:compute_layout": 2,
        "<GC>": 7,
        "app.py:render_loop": 11,
        "renderers.py:render": 13,
        "selectors.py:EpollSelector.select": 17,
    }


def test_summary_counts_inclusive_samples_only_below_each_stage_root() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.inclusive_samples == {
        "layout.py:compute_layout": 7,
        "layout.py:_measure_text": 5,
        "paint.py:paint_layout": 7,
        "<GC>": 7,
        "capture.py:run_sink": 13,
        "renderers.py:render": 13,
        "selectors.py:EpollSelector.select": 17,
    }
