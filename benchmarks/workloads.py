"""Every workload, by name, for the CLI and the smoke tests."""

from benchmarks import agent, canvas, dashboard, top
from benchmarks.harness import Runnable

WORKLOADS: dict[str, Runnable] = {
    workload.name: workload for workload in (canvas.WORKLOAD, top.WORKLOAD, agent.WORKLOAD, dashboard.WORKLOAD)
}
