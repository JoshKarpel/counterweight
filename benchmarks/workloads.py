"""Every workload, by name, for the CLI and the smoke tests."""

from benchmarks import agent
from benchmarks import agent_markdown
from benchmarks import agent_typing
from benchmarks import canvas
from benchmarks import dashboard
from benchmarks import dashboard_local
from benchmarks import document
from benchmarks import top
from benchmarks.harness import Runnable

WORKLOADS: dict[str, Runnable] = {
    workload.name: workload
    for workload in (
        canvas.WORKLOAD,
        canvas.ELEMENT_WORKLOAD,
        top.WORKLOAD,
        top.MEMO_WORKLOAD,
        agent.WORKLOAD,
        agent.MEMO_WORKLOAD,
        agent.SCROLLED_WORKLOAD,
        agent_typing.WORKLOAD,
        agent_markdown.WORKLOAD,
        agent_markdown.MEMO_WORKLOAD,
        dashboard.WORKLOAD,
        dashboard.MEMO_WORKLOAD,
        dashboard_local.WORKLOAD,
        document.WORKLOAD,
        document.LINES_WORKLOAD,
        document.TEXT_AREA_WORKLOAD,
    )
}
