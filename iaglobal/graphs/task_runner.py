import inspect
import asyncio
from typing import Any, Dict

from .node import Node
from .execution_context import ExecutionContext


class TaskRunner:
    async def run(self, node: Node, ctx: Dict[str, Any]) -> Any:
        fn = node.run
        if fn is None:
            return {"output": None}

        exec_ctx = ExecutionContext(task_id=node.name, graph_state=ctx)
        enriched_ctx = {**ctx, "_exec_ctx": exec_ctx}

        if inspect.iscoroutinefunction(fn):
            return await fn(enriched_ctx)

        if asyncio.iscoroutine(fn):
            return await fn

        return await asyncio.to_thread(fn, enriched_ctx)
