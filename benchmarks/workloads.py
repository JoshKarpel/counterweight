"""Every workload, by name, for the CLI and the smoke tests."""

from benchmarks import agent, agent_markdown, agent_typing, canvas, dashboard, dashboard_local, document, top
from benchmarks.harness import Runnable

WORKLOADS: dict[str, Runnable] = {
    workload.name: workload
    for workload in (
        canvas.WORKLOAD,
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
