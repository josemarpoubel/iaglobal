# iaglobal/providers/provider_metrics.py

"""
Provider Metrics Engine
=======================

Responsável por coletar e armazenar métricas de performance dos providers:

- Latência (ms)
- Sucesso / falha
- Modelo utilizado
- Tipo de tarefa
- Tokens (prompt, completion, total)
- Custo estimado
- Timestamp

Design:
- leve (CPU-friendly)
- sem dependência externa obrigatória
- pronto para SQLite ou JSONL
"""

import json
import os
import time
from typing import Dict, Any, Optional, List

from iaglobal.utils.logger import logger


# =========================================================
# STORAGE PATH
# =========================================================

from iaglobal._paths import PROVIDER_METRICS_DIR

BASE_DIR = PROVIDER_METRICS_DIR
BASE_DIR.mkdir(parents=True, exist_ok=True)

METRICS_FILE = str(BASE_DIR / "metrics.jsonl")

# Cache do aggregator
_aggregator_cache = None
_aggregator_cache_ts = 0.0


# =========================================================
# PRICING TABLE ($/1K tokens)
# =========================================================
# Fontes aproximadas (públicas). Valores em USD por 1K tokens.
# Modelo genérico = fallback quando o modelo exato não está listado.

PRICING: Dict[str, Dict[str, float]] = {
    # ── OpenRouter ──
    "openrouter/meta-llama/llama-3.1-8b-instruct":       {"input": 0.00018,  "output": 0.00018},
    "openrouter/meta-llama/llama-3.3-70b-instruct":      {"input": 0.00059,  "output": 0.00079},
    "openrouter/mistralai/mixtral-8x22b-instruct":       {"input": 0.00090,  "output": 0.00090},
    "openrouter/anthropic/claude-3.5-sonnet":             {"input": 0.00300,  "output": 0.01500},
    "openrouter/openai/gpt-4o":                           {"input": 0.00250,  "output": 0.01000},
    "openrouter/deepseek/deepseek-chat":                  {"input": 0.00014,  "output": 0.00028},
    # fallback genérico openrouter
    "openrouter/*":                                       {"input": 0.00050,  "output": 0.00150},

    # ── Groq ──
    "groq/llama-3.1-8b-instant":                          {"input": 0.00005,  "output": 0.00008},
    "groq/llama-3.3-70b-versatile":                       {"input": 0.00059,  "output": 0.00079},
    "groq/mixtral-8x7b-32768":                            {"input": 0.00024,  "output": 0.00024},
    "groq/*":                                             {"input": 0.00010,  "output": 0.00020},

    # ── NVIDIA ──
    "nvidia/mistralai/mistral-small-4-119b-2603":                 {"input": 0.00010,  "output": 0.00010},
    "nvidia/*":                                           {"input": 0.00010,  "output": 0.00010},

    # ── OpenCode ──
    "opencode/nemotron-3-super-free":                     {"input": 0.00000,  "output": 0.00000},
    "opencode/*":                                         {"input": 0.00000,  "output": 0.00000},

    # ── Gemini ──
    "gemini/gemini-2.5-flash-lite":                       {"input": 0.000075, "output": 0.00030},
    "gemini/gemini-2.5-pro":                              {"input": 0.00125,  "output": 0.00500},
    "gemini/*":                                           {"input": 0.00010,  "output": 0.00040},

    # ── Ollama (local, custo zero) ──
    "ollama/*":                                           {"input": 0.0,     "output": 0.0},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estima custo em USD baseado na tabela PRICING."""
    key = model if model in PRICING else None
    if not key:
        # Tenta wildcard por provider
        provider = model.split("/")[0] if "/" in model else model
        wildcard = f"{provider}/*"
        key = wildcard if wildcard in PRICING else None
    if not key:
        return 0.0
    p = PRICING[key]
    return (p["input"] * prompt_tokens + p["output"] * completion_tokens) / 1000.0


# =========================================================
# CORE METRICS ENGINE
# =========================================================

class ProviderMetrics:

    def __init__(self):
        self.buffer: List[Dict[str, Any]] = []

    # =====================================================
    # RECORD EVENT
    # =====================================================

    def record(
        self,
        provider: str,
        model: str,
        prompt: str,
        success: bool,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost: float = 0.0,
        task_type: Optional[str] = None
    ) -> None:

        event = {
            "timestamp": time.time(),
            "provider": provider,
            "model": model,
            "prompt_size": len(prompt),
            "success": success,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "task_key": f"{task_type or 'unknown'}",
            "task_type": task_type or "unknown"
        }

        self.buffer.append(event)
        logger.info("[METRICS] record provider=%s model=%s success=%s latency_ms=%.0f tokens=%d cost=%.6f task=%s",
                     provider, model, success, latency_ms, total_tokens, cost, task_type or "unknown")

        # flush automático leve (evita perda)
        if len(self.buffer) >= 10:
            self.flush()

    def get_task_model_stats(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Estrutura:
        {
            model: {
                task_type: {metrics}
            }
        }
        """

        if not os.path.exists(METRICS_FILE):
            return {}

        stats = {}

        with open(METRICS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)

                    model = data["model"]
                    task = data.get("task_type", "unknown")

                    if model not in stats:
                        stats[model] = {}

                    if task not in stats[model]:
                        stats[model][task] = {
                            "calls": 0,
                            "success": 0,
                            "latency": 0.0,
                            "cost": 0.0
                        }

                    s = stats[model][task]

                    s["calls"] += 1
                    s["success"] += int(data["success"])
                    s["latency"] += data["latency_ms"]
                    s["cost"] += data.get("cost", 0.0)

                except Exception:
                    continue

        # normalização
        for model in stats:
            for task in stats[model]:
                s = stats[model][task]
                calls = max(s["calls"], 1)

                s["success_rate"] = s["success"] / calls
                s["avg_latency"] = s["latency"] / calls
                s["avg_cost"] = s["cost"] / calls

        return stats

    # =====================================================
    # FLUSH TO DISK (JSONL)
    # =====================================================

    def flush(self) -> None:
        if not self.buffer:
            return

        try:
            with open(METRICS_FILE, "a", encoding="utf-8") as f:
                for item in self.buffer:
                    f.write(json.dumps(item) + "\n")

            self.buffer.clear()

        except Exception as e:
            print(f"⚠️ Metrics flush error: {e}")

    # =====================================================
    # ANALYTICS (BASIC SCORE ENGINE)
    # =====================================================

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Calcula estatísticas por provider com tokens e custo."""

        if not os.path.exists(METRICS_FILE):
            return {}

        stats = {}

        with open(METRICS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    provider = data["provider"]

                    if provider not in stats:
                        stats[provider] = {
                            "calls": 0,
                            "success": 0,
                            "total_latency": 0.0,
                            "total_cost": 0.0,
                            "total_prompt_tokens": 0,
                            "total_completion_tokens": 0,
                            "total_tokens": 0,
                        }

                    s = stats[provider]
                    s["calls"] += 1
                    s["success"] += int(data["success"])
                    s["total_latency"] += data["latency_ms"]
                    s["total_cost"] += data["cost"]
                    s["total_prompt_tokens"] += data.get("prompt_tokens", 0)
                    s["total_completion_tokens"] += data.get("completion_tokens", 0)
                    s["total_tokens"] += data.get("total_tokens", 0)

                except Exception:
                    continue

        # normalização
        for p in stats:
            s = stats[p]
            s["success_rate"] = s["success"] / max(s["calls"], 1)
            s["avg_latency"] = s["total_latency"] / max(s["calls"], 1)
            s["avg_tokens"] = s["total_tokens"] / max(s["calls"], 1)
            s["avg_cost"] = s["total_cost"] / max(s["calls"], 1)

        return stats

    def get_model_stats(self) -> Dict[str, Dict[str, Any]]:
        """Calcula estatísticas por modelo (mais granular que provider)."""
        if not os.path.exists(METRICS_FILE):
            return {}

        stats = {}

        with open(METRICS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    model = data["model"]

                    if model not in stats:
                        stats[model] = {
                            "provider": data["provider"],
                            "calls": 0,
                            "success": 0,
                            "total_latency": 0.0,
                            "total_cost": 0.0,
                            "total_prompt_tokens": 0,
                            "total_completion_tokens": 0,
                            "total_tokens": 0,
                        }

                    s = stats[model]
                    s["calls"] += 1
                    s["success"] += int(data["success"])
                    s["total_latency"] += data["latency_ms"]
                    s["total_cost"] += data["cost"]
                    s["total_prompt_tokens"] += data.get("prompt_tokens", 0)
                    s["total_completion_tokens"] += data.get("completion_tokens", 0)
                    s["total_tokens"] += data.get("total_tokens", 0)

                except Exception:
                    continue

        for m in stats:
            s = stats[m]
            s["success_rate"] = s["success"] / max(s["calls"], 1)
            s["avg_latency"] = s["total_latency"] / max(s["calls"], 1)
            s["avg_tokens"] = s["total_tokens"] / max(s["calls"], 1)
            s["avg_cost"] = s["total_cost"] / max(s["calls"], 1)

        return stats

    # =====================================================
    # SIMPLE SCORE (BASE PARA BANDIT FUTURO)
    # =====================================================

    def score_provider(self, provider: str) -> float:
        """
        Score simples inicial (será substituído por UCB1 depois)
        """

        stats = self.get_provider_stats()

        if provider not in stats:
            return 0.5  # neutral

        s = stats[provider]

        success = s["success_rate"]
        latency_penalty = min(s["avg_latency"] / 1000, 1.0)  # normaliza

        score = (success * 0.7) - (latency_penalty * 0.3)

        return max(0.0, min(score, 1.0))


# =========================================================
# SINGLETON GLOBAL
# =========================================================

metrics = ProviderMetrics()



def format_metrics_report(stats: Dict[str, Dict[str, Any]], title: str = "Provider Metrics") -> str:
    """Formata estatísticas como tabela terminal."""
    if not stats:
        return f"  (no data)"

    lines = []
    lines.append(f"  {'─' * 72}")
    lines.append(f"  {title}")
    lines.append(f"  {'─' * 72}")
    lines.append(f"  {'Provider/Model':<45} {'Calls':>6} {'Succ%':>7} {'Avg ms':>8} {'Tokens':>8} {'Cost $':>10}")
    lines.append(f"  {'─' * 72}")

    for name, s in sorted(stats.items(), key=lambda x: -x[1]["calls"]):
        short_name = name[:44] if len(name) > 44 else name
        succ_pct = s["success_rate"] * 100
        avg_ms = s["avg_latency"]
        avg_tok = s.get("avg_tokens", 0)
        avg_cost = s.get("avg_cost", 0)
        lines.append(
            f"  {short_name:<45} {s['calls']:>6} {succ_pct:>6.0f}% {avg_ms:>7.0f} {avg_tok:>7.0f} {avg_cost:>9.6f}"
        )

    lines.append(f"  {'─' * 72}")
    return "\n".join(lines)
