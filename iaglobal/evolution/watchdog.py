# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
EvolutionaryWatchdog — Monitor de padrões evolutivos no ancestry_tree.

Tradução das Leis de Holliwell:
- Lei 4 (Colheita): Padrões repetitivos são sementes de ferramentas permanentes.
- Lei 6 (Amor): Reconheça tarefas recorrentes; registre-as como anticorpos locais.
- Lei 8 (Transmutação): Todo esforço cloud repetido pode ser transmutado em tool local.

O watchdog varre o ancestry_tree.jsonl, detecta tarefas que foram escaladas
para cloud repetidamente com sucesso, e as converte em ferramentas permanentes
na ToolLibrary — eliminando a necessidade futura de cloud.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.evolution.watchdog")

# Número mínimo de escalonamentos bem-sucedidos para considerar "Padrão Evolutivo"
MIN_PATTERN_REPETITIONS = 3
# Score mínimo de confiança para o padrão
MIN_PATTERN_CONFIDENCE = 0.85


class EvolutionaryWatchdog:
    """Monitor que analisa o ancestry_tree e detecta padrões evolutivos."""

    def __init__(self, ancestry_path: Optional[Path] = None):
        if ancestry_path is None:
            try:
                from iaglobal._paths import DATA_DIR

                ancestry_path = DATA_DIR / "ancestry_tree.jsonl"
            except Exception:
                import tempfile

                ancestry_path = (
                    Path(tempfile.gettempdir()) / "iaglobal_ancestry_tree.jsonl"
                )
        self.ancestry_path = ancestry_path
        self._last_check: Dict[str, int] = {}

    def analyze(self) -> List[Dict[str, Any]]:
        """Varre ancestry_tree.jsonl e retorna padrões evolutivos detectados.

        Returns:
            Lista de dicionários com:
              - task_hash: str
              - count: int (número de escalonamentos)
              - task_summary: str (primeiro resumo encontrado)
              - confidence: float (taxa de sucesso)
        """
        if not self.ancestry_path.exists():
            logger.debug(
                "[WATCHDOG] ancestry_tree nao encontrado: %s", self.ancestry_path
            )
            return []

        records: List[Dict] = []
        try:
            with open(str(self.ancestry_path)) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning("[WATCHDOG] Erro ao ler ancestry: %s", e)
            return []

        # Filtrar apenas Cognitive_Escalation com sucesso
        escalations = [
            r
            for r in records
            if r.get("type") == "Cognitive_Escalation" and r.get("success") is True
        ]

        if not escalations:
            return []

        # Agrupar por task_hash
        task_groups: Dict[str, List[Dict]] = defaultdict(list)
        for rec in escalations:
            th = rec.get("task_hash")
            if th:
                task_groups[th].append(rec)

        patterns: List[Dict[str, Any]] = []
        for task_hash, group in task_groups.items():
            count = len(group)
            if count < MIN_PATTERN_REPETITIONS:
                continue

            # Calcular confiança — média de linhas de sucesso
            successes = sum(1 for g in group if g.get("success") is True)
            confidence = successes / count if count > 0 else 0.0

            if confidence < MIN_PATTERN_CONFIDENCE:
                continue

            task_summary = group[0].get("task_summary", "")
            patterns.append(
                {
                    "task_hash": task_hash,
                    "count": count,
                    "task_summary": task_summary,
                    "confidence": round(confidence, 2),
                }
            )

        if patterns:
            logger.info("[WATCHDOG] Padroes evolutivos detectados: %d", len(patterns))
            for p in patterns:
                logger.info(
                    "[WATCHDOG]   task_hash=%s count=%d conf=%.2f sum='%s'",
                    p["task_hash"],
                    p["count"],
                    p["confidence"],
                    p["task_summary"][:50],
                )

        return patterns

    def should_register_tool(self, task_hash: str) -> bool:
        """Verifica se uma task_hash específica atingiu o padrão evolutivo."""
        patterns = self.analyze()
        for p in patterns:
            if p["task_hash"] == task_hash:
                return True
        return False

    def register_tool_from_pattern(
        self, pattern: Dict[str, Any], code: str
    ) -> Optional[str]:
        """Registra uma tool na ToolLibrary a partir de um padrão evolutivo.

        Args:
            pattern: Dicionário com task_hash, task_summary etc.
            code: Código funcional da ferramenta a ser registrada.

        Returns:
            Nome da tool registrada ou None.
        """
        try:
            from iaglobal.tools.tool_library import tool_library

            task = pattern.get("task_summary", pattern["task_hash"])
            name = tool_library.register_from_code(task, code)
            if name:
                logger.info(
                    "[WATCHDOG] Tool registrada do padrao evolutivo: %s (task_hash=%s)",
                    name,
                    pattern["task_hash"],
                )
                from iaglobal.obsidian.omnimind import omni_mind

                omni_mind.emitir_gatilho_apoptose(
                    "evolutionary_watchdog",
                    f"Tool registrada por padrao evolutivo: {name} para task_hash={pattern['task_hash']}",
                )
            return name
        except Exception as e:
            logger.warning("[WATCHDOG] Falha ao registrar tool do padrao: %s", e)
            return None

    def clear_detected_pattern(self, task_hash: str) -> None:
        """Remove um padrão da memória para evitar re-registro."""
        self._last_check[task_hash] = 0

    def get_pattern_count(self, task_hash: str) -> int:
        """Retorna quantas vezes uma task_hash foi escalada com sucesso."""
        patterns = self.analyze()
        for p in patterns:
            if p["task_hash"] == task_hash:
                return p["count"]
        return 0


watchdog = EvolutionaryWatchdog()
