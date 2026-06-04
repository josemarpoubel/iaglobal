import asyncio
from typing import Any, Dict

from .scheduler import Scheduler
from .task_runner import TaskRunner
from .state_store import StateStore, PENDING, RUNNING, SUCCESS, FAILED


class ExecutionEngine:
    def __init__(self, graph, max_retries: int = 3):
        self.graph = graph
        self.scheduler = Scheduler(graph)
        self.runner = TaskRunner()
        self.state = StateStore()
        self.max_retries = max_retries

        for name in graph.nodes:
            self.state.set(name, PENDING)

    async def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        while True:
            tasks = self.scheduler.ready_tasks(self.state.state)

            if not tasks:
                break

            coros = [self._execute(task, ctx) for task in tasks]
            await asyncio.gather(*coros)

        return dict(self.state.state)

    async def _execute(self, task, ctx: Dict[str, Any]) -> None:
        name = task.id
        attempt = task.attempt

        while attempt <= self.max_retries:
            self.state.set(name, RUNNING, attempt=attempt)

            try:
                node_ctx = {**ctx, "state": self.state}
                output = await self.runner.run(task.node, node_ctx)

                result_text = ""
                if isinstance(output, dict):
                    result_text = output.get("output", output.get("result_text", ""))
                    if not isinstance(result_text, str):
                        result_text = str(result_text) if result_text is not None else ""
                elif output is not None:
                    result_text = str(output)

                self.state.set(name, SUCCESS, output=result_text, attempt=attempt)
                return

            except Exception as e:
                attempt += 1
                self.state.set(name, FAILED, error=str(e), attempt=attempt)

        self.state.set(name, FAILED, error=f"Max retries ({self.max_retries}) exceeded",
                       attempt=attempt)
