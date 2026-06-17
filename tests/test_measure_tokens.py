# test_measure_tokens.py

# benchmark_iaglobal.py  — Geração 2
from __future__ import annotations

import asyncio
import json
import re
import time
import pathlib
import statistics
from dataclasses import dataclass, field
from typing import Optional

from iaglobal import _paths
from tqdm.asyncio import tqdm_asyncio


# ── Configuração imutável ────────────────────────────────────────────────────

@dataclass(frozen=True)
class BenchmarkConfig:
    command: str
    iterations: int = 10
    max_workers: int = 10          # paralelismo controlado
    timeout_per_run: float = 30.0  # segundos por execução
    log_file: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(_paths.LOG_DIR) / "app.log"
    )

    # Padrões compilados uma vez
    TOKEN_RE: re.Pattern = field(init=False, repr=False)
    CACHE_RE: re.Pattern = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # frozen=True exige object.__setattr__ para atributos derivados
        object.__setattr__(self, "TOKEN_RE",
            re.compile(r'"?tokens"?\s*:\s*(\d+)', re.IGNORECASE))
        object.__setattr__(self, "CACHE_RE",
            re.compile(r"SUCCESS local|cache hit", re.IGNORECASE))


# ── Resultado tipado por execução ────────────────────────────────────────────

@dataclass
class ExecutionResult:
    returncode: int
    duration_ms: float
    stdout: str = ""
    stderr: str = ""

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


# ── Executor assíncrono ──────────────────────────────────────────────────────

async def run_once(cfg: BenchmarkConfig) -> ExecutionResult:
    t0 = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_shell(
            f'iaglobal run "{cfg.command}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=cfg.timeout_per_run
        )
        elapsed = (time.perf_counter() - t0) * 1000
        return ExecutionResult(
            returncode=proc.returncode or 0,
            duration_ms=elapsed,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )
    except asyncio.TimeoutError:
        return ExecutionResult(returncode=-1, duration_ms=cfg.timeout_per_run * 1000)
    except Exception as exc:
        return ExecutionResult(returncode=-2, duration_ms=(time.perf_counter() - t0) * 1000, stderr=f"Unexpected error: {type(exc).__name__} - {str(exc)}")


async def run_all(cfg: BenchmarkConfig) -> list[ExecutionResult]:
    sem = asyncio.Semaphore(cfg.max_workers)

    async def bounded(i: int) -> ExecutionResult:
        async with sem:
            return await run_once(cfg)

    tasks = [bounded(i) for i in range(cfg.iterations)]
    return await tqdm_asyncio.gather(*tasks, desc=f"Executando {cfg.iterations} tarefas")


# ── Parser de log estruturado ────────────────────────────────────────────────

@dataclass
class LogMetrics:
    token_samples: list[int] = field(default_factory=list)
    cache_hits: int = 0

    def ingest_line(self, line: str, cfg: BenchmarkConfig) -> None:
        m = cfg.TOKEN_RE.search(line)
        if m:
            self.token_samples.append(int(m.group(1)))
        if cfg.CACHE_RE.search(line):
            self.cache_hits += 1


# ── Agregador de métricas ────────────────────────────────────────────────────

@dataclass
class BenchmarkReport:
    iterations: int
    successes: int
    failures: int
    latencies_ms: list[float]
    token_samples: list[int]
    cache_hits: int

    def summary(self) -> dict:
        lats = self.latencies_ms or [0]
        toks = self.token_samples or [0]
        return {
            "iterations": self.iterations,
            "success_rate_%": round(self.successes / self.iterations * 10, 1),
            "error_rate_%": round(self.failures / self.iterations * 10, 1),
            "latency_ms": {
                "min": round(min(lats), 1),
                "median": round(statistics.median(lats), 1),
                "p95": round(
                    sorted(lats)[int(len(lats) * 0.95)], 1
                ) if len(lats) > 1 else round(lats[0], 1),
                "max": round(max(lats), 1),
            },
            "tokens": {
                "total": sum(toks),
                "min": min(toks),
                "max": max(toks),
                "avg": round(statistics.mean(toks), 1) if toks else 0,
                "p95": round(
                    sorted(toks)[int(len(toks) * 0.95)], 1
                ) if len(toks) > 1 else (toks[0] if toks else 0),
            },
            "cache_hits": self.cache_hits,
            "cache_rate_%": round(self.cache_hits / self.iterations * 10, 1),
        }

    def print(self) -> None:
        s = self.summary()
        print("\n=== BENCHMARK REPORT ===")
        print(json.dumps(s, indent=2, ensure_ascii=False))


# ── Orquestrador principal ───────────────────────────────────────────────────

async def run_benchmark(cfg: BenchmarkConfig) -> BenchmarkReport:
    # 1. Rotaciona log para não acumular runs anteriores
    if cfg.log_file.exists():
        rotated = cfg.log_file.with_suffix(".prev.log")
        cfg.log_file.rename(rotated)

    # 2. Executa todas as iterações
    results = await run_all(cfg)

    # 3. Parseia log gerado
    log_metrics = LogMetrics()
    if cfg.log_file.exists():
        for line in cfg.log_file.read_text(errors="replace").splitlines():
            log_metrics.ingest_line(line, cfg)

    # 4. Agrega
    successes = sum(1 for r in results if r.succeeded)
    return BenchmarkReport(
        iterations=cfg.iterations,
        successes=successes,
        failures=cfg.iterations - successes,
        latencies_ms=[r.duration_ms for r in results],
        token_samples=log_metrics.token_samples,
        cache_hits=log_metrics.cache_hits,
    )


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = BenchmarkConfig(
        command="crie uma calculadora em php com tema escuro",
        iterations=10,
        max_workers=10,
        timeout_per_run=180.0,
    )
    report = asyncio.run(run_benchmark(cfg))
    report.print()
