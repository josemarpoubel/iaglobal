import asyncio
import os
import time
import hashlib
from pathlib import Path
from typing import Optional

from iaglobal._paths import MEMORY_DIR

WORK_ROOT = MEMORY_DIR / "work"


class WorkDir:
    __slots__ = ("agent", "execution_id", "root", "code", "output", "cache", "tests", "logs")

    def __init__(self, agent: str, execution_id: str):
        self.agent = agent
        self.execution_id = execution_id
        safe_agent = agent.replace("/", "_").replace(" ", "_")
        safe_eid = execution_id.replace("/", "_").replace(" ", "_")
        self.root = WORK_ROOT / safe_agent / safe_eid
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

    def write_code(self, code: str):
        self.code.write_text(code, encoding="utf-8")
        return self

    async def async_write_code(self, code: str):
        await asyncio.to_thread(self.code.write_text, code, encoding="utf-8")
        return self

    def write_output(self, text: str):
        self.output.write_text(text, encoding="utf-8")
        return self

    async def async_write_output(self, text: str):
        await asyncio.to_thread(self.output.write_text, text, encoding="utf-8")
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

    def write_test(self, name: str, content: str):
        path = self.tests / name
        path.write_text(content, encoding="utf-8")
        return self

    async def async_write_test(self, name: str, content: str):
        def _write():
            path = self.tests / name
            path.write_text(content, encoding="utf-8")
        await asyncio.to_thread(_write)
        return self

    def exists(self) -> bool:
        return self.root.exists()

    def __repr__(self):
        return "WorkDir(%s)" % self.root


def make_workdir(agent_name: str, execution_id: str, task: str = "") -> WorkDir:
    eid = execution_id or hashlib.md5(task.encode()).hexdigest()[:12]
    return WorkDir(agent_name, eid).ensure()


def clean_workdir(agent_name: str, execution_id: str):
    safe_agent = agent_name.replace("/", "_").replace(" ", "_")
    safe_eid = execution_id.replace("/", "_").replace(" ", "_")
    path = WORK_ROOT / safe_agent / safe_eid
    import shutil
    if path.exists():
        shutil.rmtree(path)


def clean_all_workdirs(max_age_hours: int = 24):
    import shutil
    now = time.time()
    for agent_dir in WORK_ROOT.iterdir():
        if not agent_dir.is_dir():
            continue
        for exec_dir in agent_dir.iterdir():
            if exec_dir.is_dir():
                age = now - exec_dir.stat().st_mtime
                if age > max_age_hours * 3600:
                    shutil.rmtree(exec_dir, ignore_errors=True)


def list_workdirs() -> list[dict]:
    result = []
    for agent_dir in sorted(WORK_ROOT.iterdir()):
        if not agent_dir.is_dir():
            continue
        for exec_dir in sorted(agent_dir.iterdir()):
            has_code = (exec_dir / "code.py").exists()
            has_output = (exec_dir / "output.txt").exists()
            has_tests = (exec_dir / "tests").exists() and any((exec_dir / "tests").iterdir())
            result.append({
                "agent": agent_dir.name,
                "execution": exec_dir.name,
                "path": str(exec_dir),
                "has_code": has_code,
                "has_output": has_output,
                "has_tests": has_tests,
                "mtime": exec_dir.stat().st_mtime,
            })
    return result
