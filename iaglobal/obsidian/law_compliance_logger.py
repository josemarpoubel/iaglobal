# iaglobal/obsidian/law_compliance_logger.py
"""
LawComplianceLogger — Registra quais leis são consultadas durante ciclos.

Gera analytics de conformidade para análise de "personalidade" do organismo.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class LawComplianceLogger:
    """
    Logger de conformidade das Leis Universais.

    Registra:
    - Quais leis foram aplicadas
    - Com que frequência
    - Em quais contextos
    """

    _instance = None
    LAW_NAMES = [
        "Lei da Ordem", "Lei da Caridade", "Lei do Vácuo",
        "Lei da Homeostase", "Lei da Autofagia", "Lei da Epigenética",
        "Lei da Apoptose", "Lei da Replicação", "Lei da Cooperação",
        "Lei da Memória Imunológica"
    ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._counts: Dict[str, int] = defaultdict(int)
        self._context_log: List[Dict[str, Any]] = []
        self._log_path = Path("iaglobal/obsidian/02_Short_Term/law_compliance_log.md")

    def log_law_application(self, law: str, context: str, agent: str) -> None:
        """Registra aplicação de lei."""
        self._counts[law] += 1

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "law": law,
            "context": context,
            "agent": agent,
        }
        self._context_log.append(entry)

        if len(self._context_log) % 100 == 0:
            asyncio.create_task(self._flush_to_obsidian_async())

    def get_top_laws(self, limit: int = 5) -> List[tuple]:
        """Retorna as leis mais aplicadas."""
        sorted_laws = sorted(self._counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_laws[:limit]

    async def _flush_to_obsidian_async(self) -> None:
        """Persiste log no Obsidian Short Term de forma assíncrona."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

            content = f"""---
id: "law_compliance_log"
tipo: "ConformidadeUniversal"
timestamp: "{datetime.now(timezone.utc).isoformat()}"
total_aplicacoes: {sum(self._counts.values())}
---

# Registro de Conformidade Universal

## Contagens por Lei
"""
            for law, count in self._counts.items():
                content += f"\n- {law}: {count} aplicações"

            def _write():
                self._log_path.write_text(content, encoding="utf-8")

            await asyncio.to_thread(_write)
        except Exception as e:
            logger.warning(f"[LAW-LOG] Falha ao persistir: {e}")

    async def flush_now(self) -> None:
        """Força flush imediato do log."""
        await self._flush_to_obsidian_async()


# Singleton
law_compliance_logger = LawComplianceLogger()