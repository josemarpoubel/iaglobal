# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""FailureAnalysisAgent — analisa logs de falha, dados reais do sistema e métricas de provedores."""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from iaglobal._paths import ERROR_DIR, LOG_DIR, JSON_DIR, PROVIDER_METRICS_DIR
from iaglobal.utils.logger import logger

PATTERNS = {
    "syntax_error": r"SyntaxError|IndentationError|NameError|TypeError",
    "import_error": r"ModuleNotFoundError|ImportError|No module named",
    "security": r"sql injection|xss|command injection|path traversal|pickle\.loads|eval\(|exec\(",
    "hallucination": r"unknown library|fake_module|nonexistent|não encontrad[ao]",
    "timeout": r"timeout|Timeout|timed out|deadline exceeded",
    "api_error": r"401|403|404|500|Unauthorized|Forbidden|Rate limit|quota",
}

_ERRORS_PATH = JSON_DIR / "errors.json"
_METRICS_PATH = PROVIDER_METRICS_DIR / "metrics.jsonl"
_LOG_PATH = LOG_DIR / "app.log"
_RESULTS_DIR = ERROR_DIR


class FailureAnalysisAgent:
    """Analisa logs de falha, dados reais do sistema e métricas de provedores."""

    @classmethod
    def collect_system_data(cls) -> Dict[str, Any]:
        """Coleta dados reais de falhas do sistema de múltiplas fontes."""
        return {
            "errors": cls._collect_errors(),
            "metrics": cls._collect_metrics(),
            "logs": cls._collect_logs(),
            "collected_at": datetime.utcnow().isoformat(),
        }

    @classmethod
    def _collect_errors(cls) -> Dict[str, Any]:
        """Lê errors.json e retorna resumo das falhas."""
        try:
            if not _ERRORS_PATH.exists():
                return {"total": 0, "entries": [], "path": str(_ERRORS_PATH)}
            data = json.loads(_ERRORS_PATH.read_text())
            errors = data.get("runtime_errors", [])
            by_component: Dict[str, int] = {}
            for err in errors:
                comp = err.get("component", "unknown")
                by_component[comp] = by_component.get(comp, 0) + 1
            return {
                "total": len(errors),
                "by_component": by_component,
                "entries": errors[-20:],
                "path": str(_ERRORS_PATH),
            }
        except Exception as e:
            logger.debug("[FAILURE_AGENT] Erro lendo errors.json: %s", e)
            return {"total": 0, "entries": [], "error": str(e)}

    @classmethod
    def _collect_metrics(cls) -> Dict[str, Any]:
        """Lê metrics.jsonl e retorna estatísticas dos provedores."""
        try:
            if not _METRICS_PATH.exists():
                return {"total_calls": 0, "by_provider": {}}
            lines = _METRICS_PATH.read_text().strip().splitlines()
            entries = [json.loads(l) for l in lines if l.strip()]
            if not entries:
                return {"total_calls": 0, "by_provider": {}}
            by_provider: Dict[str, Dict] = {}
            for e in entries:
                prov = e.get("provider", "unknown")
                if prov not in by_provider:
                    by_provider[prov] = {"calls": 0, "success": 0, "failures": 0, "total_latency_ms": 0}
                by_provider[prov]["calls"] += 1
                if e.get("success"):
                    by_provider[prov]["success"] += 1
                else:
                    by_provider[prov]["failures"] += 1
                by_provider[prov]["total_latency_ms"] += e.get("latency_ms", 0)
            for prov, stats in by_provider.items():
                stats["avg_latency_ms"] = round(stats["total_latency_ms"] / stats["calls"], 1) if stats["calls"] else 0
                stats["success_rate"] = round(stats["success"] / stats["calls"] * 100, 1) if stats["calls"] else 0
            return {
                "total_calls": len(entries),
                "by_provider": by_provider,
                "path": str(_METRICS_PATH),
            }
        except Exception as e:
            logger.debug("[FAILURE_AGENT] Erro lendo metrics.jsonl: %s", e)
            return {"total_calls": 0, "by_provider": {}, "error": str(e)}

    @classmethod
    def _collect_logs(cls, max_lines: int = 50) -> Dict[str, Any]:
        """Lê as últimas N linhas do app.log."""
        try:
            if not _LOG_PATH.exists():
                return {"lines": 0, "content": ""}
            text = _LOG_PATH.read_text(encoding="utf-8", errors="replace")
            lines = text.strip().splitlines()
            tail = lines[-max_lines:]
            return {
                "lines": len(lines),
                "tail_lines": len(tail),
                "content": "\n".join(tail),
                "path": str(_LOG_PATH),
            }
        except Exception as e:
            logger.debug("[FAILURE_AGENT] Erro lendo app.log: %s", e)
            return {"lines": 0, "content": "", "error": str(e)}

    @classmethod
    def generate_report(cls, system_data: Dict[str, Any]) -> str:
        """Gera relatório markdown a partir dos dados coletados."""
        lines = []
        errors = system_data.get("errors", {})
        metrics = system_data.get("metrics", {})
        logs = system_data.get("logs", {})

        lines.append("# Relatório de Falhas do Sistema\n")
        lines.append(f"_Gerado em: {system_data.get('collected_at', 'N/A')}_\n")

        # Seção: Erros
        lines.append("## 1. Erros Registrados\n")
        if errors.get("total", 0) > 0:
            lines.append(f"**Total de erros:** {errors['total']}\n")
            if errors.get("by_component"):
                lines.append("\n**Por componente:**\n")
                for comp, count in sorted(errors["by_component"].items(), key=lambda x: -x[1]):
                    lines.append(f"- `{comp}`: {count} ocorrência(s)")
                lines.append("")
            lines.append("\n**Últimos erros:**\n")
            for err in errors.get("entries", [])[-5:]:
                ts = err.get("timestamp", "?")[11:19]
                msg = err.get("message", "?")[:120]
                comp = err.get("component", "?")
                lines.append(f"- [{ts}] `{comp}`: {msg}")
            lines.append("")
        else:
            lines.append("Nenhum erro registrado.\n")

        # Seção: Métricas de provedores
        lines.append("## 2. Métricas de Provedores\n")
        if metrics.get("total_calls", 0) > 0:
            lines.append(f"**Total de chamadas:** {metrics['total_calls']}\n")
            for prov, stats in sorted(metrics.get("by_provider", {}).items()):
                lines.append(
                    f"- **{prov}**: {stats['calls']} chamadas, "
                    f"{stats['success_rate']}% sucesso, "
                    f"média {stats['avg_latency_ms']}ms"
                )
            lines.append("")
        else:
            lines.append("Nenhuma métrica registrada.\n")

        # Seção: Logs recentes (apenas WARNING/ERROR)
        lines.append("## 3. Eventos Recentes (WARNING/ERROR)\n")
        if logs.get("content"):
            warning_lines = [
                l for l in logs["content"].splitlines()
                if "WARNING" in l or "ERROR" in l or "CRITICAL" in l
            ]
            if warning_lines:
                for wl in warning_lines[-10:]:
                    lines.append(f"- `{wl[:150]}`")
            else:
                lines.append("Nenhum evento WARNING/ERROR nos últimos logs.\n")
            lines.append("")
        else:
            lines.append("Logs não disponíveis.\n")

        return "\n".join(lines)

    @classmethod
    def persist_report(cls, system_data: Dict[str, Any], report: str) -> Dict[str, str]:
        """Salva relatório markdown e dados JSON na pasta error/."""
        try:
            _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            md_path = _RESULTS_DIR / f"failure_report_{ts}.md"
            md_path.write_text(report, encoding="utf-8")

            json_path = _RESULTS_DIR / f"failure_data_{ts}.json"
            json_path.write_text(json.dumps(system_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

            logger.info("[FAILURE_AGENT] Relatório salvo: %s", md_path)
            logger.info("[FAILURE_AGENT] Dados salvos: %s", json_path)
            return {"report_path": str(md_path), "data_path": str(json_path)}
        except Exception as e:
            logger.exception("[FAILURE_AGENT] Erro ao persistir relatório: %s", e)
            return {"error": str(e)}

    @classmethod
    def analyze(cls, error_log: str, prompt: str = "", code: str = "") -> Dict[str, Any]:
        findings = []
        guardrail_suggestions = []

        for category, pattern in PATTERNS.items():
            matches = re.findall(pattern, error_log, re.IGNORECASE)
            if matches:
                findings.append({"category": category, "matches": len(matches), "detail": matches[:3]})

                if category == "syntax_error":
                    guardrail_suggestions.append({
                        "type": "ast_validator",
                        "rule": "compile_check",
                        "description": "Validar sintaxe via compile() antes de executar",
                    })
                elif category == "import_error":
                    guardrail_suggestions.append({
                        "type": "import_blocklist",
                        "rule": f"block_unknown_{matches[0].lower() if matches else 'module'}",
                        "description": f"Bloquear import de módulos não verificados",
                    })
                elif category == "security":
                    guardrail_suggestions.append({
                        "type": "pattern_block",
                        "rule": "security_hotfix",
                        "description": f"Bloquear padrão: {matches[0] if matches else 'security'}",
                    })
                elif category == "hallucination":
                    guardrail_suggestions.append({
                        "type": "regex_ban",
                        "rule": "anti_hallucination",
                        "description": "Banir bibliotecas inexistentes via regex",
                    })

        return {
            "error_type": findings[0]["category"] if findings else "unknown",
            "findings": findings,
            "suggestion_count": len(guardrail_suggestions),
            "guardrail_suggestions": guardrail_suggestions,
        }

    @classmethod
    def generate_guardrail(cls, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if analysis["suggestion_count"] == 0:
            return None
        suggestion = analysis["guardrail_suggestions"][0]
        return {
            "name": f"guardrail_{analysis['error_type']}_{hash(str(suggestion)) % 10000:04d}",
            "type": suggestion["type"],
            "rule": suggestion["rule"],
            "description": suggestion["description"],
        }
