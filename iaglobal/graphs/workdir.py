import asyncio
import os
import time
import hashlib
from pathlib import Path
from typing import Optional

from iaglobal._paths import WORK_DIR


class WorkDir:
    __slots__ = ("agent", "execution_id", "root", "code", "output", "cache", "tests", "logs")

    def __init__(self, agent: str, execution_id: str):
        self.agent = agent
        self.execution_id = execution_id
        safe_agent = agent.replace("/", "_").replace(" ", "_")
        safe_eid = execution_id.replace("/", "_").replace(" ", "_")
        self.root = WORK_DIR / safe_agent / safe_eid
        self.code = self.root / "code.py"
        self.output = self.root / "output.txt"
        self.cache = self.root / "cache"
        self.tests = self.root / "tests"
        self.logs = self.root / "logs.txt"

    def ensure(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.tests.mkdir(parents=True, exist_ok=True)
        return self

    async def async_write_code(self, code: str):
        await asyncio.to_thread(self.code.write_text, code, encoding="utf-8")
        return self

    def write_output(self, text: str):
        self.output.write_text(text, encoding="utf-8")
        return self

    def append_log(self, line: str):
        with self.logs.open("a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), line))
        return self

    async def async_append_log(self, line: str):
        def _write():
            with self.logs.open("a", encoding="utf-8") as f:
                f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), line))
        await asyncio.to_thread(_write)
        return self

    def exists(self) -> bool:
        return self.root.exists()

    def __repr__(self):
        return "WorkDir(%s)" % self.root


def make_workdir(agent_name: str, execution_id: str, task: str = "") -> WorkDir:
    eid = execution_id or hashlib.md5(task.encode()).hexdigest()[:12]
    return WorkDir(agent_name, eid).ensure()



