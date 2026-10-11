from pathlib import Path
from types import ModuleType

import pytest

from benchmarks import agent, canvas, dashboard, top
from benchmarks.harness import run
from benchmarks.stacks import APP_ITSELF, OUTSIDE_APP, Frame, parse_collapsed, parse_frame, summarize
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
tid:7;runners.py:run:195;app.py:app:296;layout.py:compute_layout:40;layout.py:_measure_text:80 5
tid:7;runners.py:run:195;app.py:app:296;layout.py:compute_layout:41 2
tid:7;runners.py:run:195;app.py:app:300;paint.py:paint_layout:60;<GC> 7
tid:7;runners.py:run:195;app.py:app:310 11
"""


def test_summary_attributes_samples_to_the_function_app_called() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.stages == {
        OUTSIDE_APP: 3,
        "layout.py:compute_layout": 7,
        "paint.py:paint_layout": 7,
        APP_ITSELF: 11,
    }
    assert (summary.total_samples, summary.app_samples) == (28, 25)


def test_summary_counts_self_samples_on_the_innermost_frame() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.self_samples == {
        "layout.py:_measure_text": 5,
        "layout.py:compute_layout": 2,
        "<GC>": 7,
        "app.py:app": 11,
    }


def test_summary_counts_inclusive_samples_only_below_app() -> None:
    summary = summarize(parse_collapsed(COLLAPSED))

    assert summary.inclusive_samples == {
        "layout.py:compute_layout": 7,
        "layout.py:_measure_text": 5,
        "paint.py:paint_layout": 7,
        "<GC>": 7,
    }
