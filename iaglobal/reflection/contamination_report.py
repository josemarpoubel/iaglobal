# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Contamination Report — Sistema de reporte de contaminação por alucinação de LLM.

Este módulo é complementar ao iaglobal/reflection/claim_detection.py:
  - claim_detection.py: DETECÇÃO e verificação (lógica centralizada)
  - contamination_report.py: REPORT e persistência (JSON auditável)

Fluxo completo:
  1. detect_architectural_claims() → claim_detection.py
  2. verify_architectural_claims() → claim_detection.py
  3. create_quarantine_report() → claim_detection.py
  4. report_architectural_hallucination() → este arquivo (JSON formal)
"""

import json
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, Any, List

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.reflection.contamination_report")


class ContaminationReport:
    """
    Reporta e previne contaminação de memória de longo prazo por alucinações de LLM.

    Mecanismo:
      1. Detecta artefatos com claims arquiteturais não-verificados
      2. Marca para revisão humana antes do ciclo REM
      3. Exige elevação de modelo para tarefas de auto-análise
    """

    def __init__(self, report_dir: Path | None = None):
        from iaglobal._paths import TEMP_DIR

        self.report_dir = report_dir or (TEMP_DIR / "reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def create_report(
        self,
        artifact_path: str,
        contamination_type: str,
        llm_model: str,
        false_claims: List[str],
        verified_facts: Dict[str, Any],
        action_taken: str,
    ) -> Path:
        """
        Cria relatório de contaminação.
        """
        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "artifact_path": artifact_path,
            "contamination_type": contamination_type,
            "llm_model": llm_model,
            "false_claims": false_claims,
            "verified_facts": verified_facts,
            "action_taken": action_taken,
            "severity": "HIGH" if "architecture" in contamination_type else "MEDIUM",
            "prevention_recommendations": self._generate_recommendations(
                contamination_type
            ),
        }

        report_file = (
            self.report_dir
            / f"contamination_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.warning(
            "🚨 [CONTAMINATION] Report created | type=%s | severity=%s | file=%s",
            contamination_type,
            report["severity"],
            report_file,
        )

        return report_file

    def _generate_recommendations(self, contamination_type: str) -> List[str]:
        """Gera recomendações de prevenção baseadas no tipo de contaminação."""

        recommendations = {
            "architectural_hallucination": [
                "Elevar modelo para tarefas de auto-análise (NVIDIA/Groq)",
                "Exigir verificação de fatos contra código-fonte antes de persistir",
                "Adicionar node de validação arquitetural pré-REM",
                "Criar lista de nodes existentes como contexto obrigatório",
            ],
            "memory_poisoning": [
                "Revisão humana obrigatória antes do ciclo REM",
                "Checksum de consistência com estado atual do sistema",
                "Expiração automática de claims arquiteturais após 7 dias",
            ],
            "false_negative_capability": [
                "Manter inventário atualizado de capabilities do sistema",
                "Cross-check com nodes registrados antes de afirmar ausência",
                "Elevação automática para modelo forte em claims de capacidade",
            ],
        }

        return recommendations.get(
            contamination_type,
            ["Revisão humana obrigatória", "Verificação de fatos com código-fonte"],
        )


# Instância global
contamination_report = ContaminationReport()


def report_architectural_hallucination(
    artifact_path: str,
    llm_model: str,
    false_claims: List[str],
    verified_facts: Dict[str, Any],
) -> Path:
    """
    Reporta alucinação arquitetural de LLM fraco.

    Exemplo de uso:
        report_architectural_hallucination(
            artifact_path="/path/to/fake_report.md",
            llm_model="qwen2.5:0.5b",
            false_claims=["iaglobal não tem busca web"],
            verified_facts={
                "nodes_existentes": ["no_search.py", "no_search_agent.py"],
            },
        )
    """
    return contamination_report.create_report(
        artifact_path=artifact_path,
        contamination_type="architectural_hallucination",
        llm_model=llm_model,
        false_claims=false_claims,
        verified_facts=verified_facts,
        action_taken="removed_before_rem_cycle",
    )


if __name__ == "__main__":
    # Exemplo: Reporta o incidente de 2026-07-07
    report_architectural_hallucination(
        artifact_path="iaglobal/memory/data/script/analysis_removed.md",
        llm_model="qwen2.5:0.5b",
        false_claims=[
            "iaglobal não possui mecanismo de busca na internet",
            "sistema é auto-contido e offline-first",
            "não há WebSearchAgent ou SearchNode",
        ],
        verified_facts={
            "nodes_existentes": [
                "no_search.py (run_search)",
                "no_search_agent.py (run_search_agent)",
                "no_search_web_brain.py (run_search_web_brain)",
                "no_search_wikipedia.py (run_search_wikipedia)",
                "_search_router.py (run_search_router)",
            ],
            "sources_implemented": [
                "DuckDuckGo",
                "Google Playwright",
                "Bing Playwright",
                "GitHub",
                "StackOverflow",
                "Grokipedia",
                "Startpage",
                "Mojeek",
                "Qwant",
                "You.com",
                "YaCy",
            ],
            "capabilities": [
                "Busca massiva em paralelo",
                "Cache em disco",
                "Roteamento inteligente de fontes",
                "Wikipedia integration",
            ],
        },
    )

    print("✅ Contamination report created successfully")
