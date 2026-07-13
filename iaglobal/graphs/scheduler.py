from typing import List

from .task import Task, PENDING, RUNNING


class Scheduler:
    def __init__(self, graph):
        self.graph = graph

    def ready_tasks(self, state) -> List[Task]:
        state_by_node = state.get("state", state) if isinstance(state, dict) else {}

        tasks = []
        for name, node in self.graph.nodes.items():
            task_key = name
            task_state = state_by_node.get(task_key, {})
            status = task_state.get("status", PENDING)

            if status == RUNNING:
                continue
            if (
                status in (Task.SUCCESS, Task.FAILED)
                if hasattr(Task, "SUCCESS")
                else status in ("SUCCESS", "FAILED")
            ):
                continue

            deps = node.depends_on or []
            all_deps_done = all(
                state_by_node.get(d, {}).get("status") in ("SUCCESS", "FAILED")
                for d in deps
            )
            if not all_deps_done:
                continue

            tasks.append(
                Task(
                    id=name,
                    node=node,
                    status=status,
                    attempt=task_state.get("attempt", 0),
                    max_retries=task_state.get("max_retries", 3),
                    output=task_state.get("output"),
                    error=task_state.get("error"),
                )
            )

        return tasks
