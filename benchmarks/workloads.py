"""Every workload, by name, for the CLI and the smoke tests."""

from benchmarks import agent, agent_markdown, canvas, dashboard, dashboard_local, top
from benchmarks.harness import Runnable

WORKLOADS: dict[str, Runnable] = {
    workload.name: workload
    for workload in (
        canvas.WORKLOAD,
        top.WORKLOAD,
        top.MEMO_WORKLOAD,
        agent.WORKLOAD,
        agent.MEMO_WORKLOAD,
        agent_markdown.WORKLOAD,
        agent_markdown.MEMO_WORKLOAD,
        dashboard.WORKLOAD,
        dashboard.MEMO_WORKLOAD,
        dashboard_local.WORKLOAD,
    )
}
