# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal/immunity/vaccine_ledger.py
===================================
VaccineLedger — persistência imunológica de failure_patterns unificada entre
vault JSON canônico (`iaglobal/memory/data/json`) e vault Obsidian (`05_Vaccines`).

Modelo biológico:
  - failure_pattern (célula T de memória) é registrado toda vez que um EvoAgent
    detecta uma falha (via FailureAnalyzer).
  - O ledger canônico é JSON em `iaglobal/memory/data/json/linhagem_<marker>.json`
    (DNA nuclear — thread-safe, fonte única da verdade).
  - O ledger Obisidian é `05_Vaccines/linhagem_<marker>.md` (RNA de expressão —
    legível por humanos, editável, indexado por tags/links).
  - Write-through: toda escrita no JSON é refletida no Obsidian em background.
  - No genesis, um EvoAgent "aplica a vacina" da própria linhagem: seu
    _failure_patterns é pré-carregado, reconhecendo ameaças já vistas pela família.
  - ImmuneMemoryExchange transporta as vacinas entre nós, mas SÓ agentes da
    mesma lineage_marker as consomem (gating evolutivo — não há autoimunidade
    entre linhagens distintas).

Async-first: toda persistência em disco vai via VaultUnifier (asyncio.to_thread).
"""

import json
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Set

from iaglobal.utils.logger import get_logger
from iaglobal.memory.vault_unifier import vault_unifier

logger = get_logger("iaglobal.immunity.vaccine_ledger")


class VaccineLedger:
    """
    Ledger de vacinas por linhagem evolutiva.

    Singleton — um único ponto de verdade para o cruzamento JSON canônico ×
    Obsidian × ImmuneMemoryExchange. Todos os EvoAgents da mesma linhagem
    compartilham o mesmo arquivo JSON + Markdown derivado.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._vault = vault_unifier
        # Linhagens conhecidas por este nó (populadas em EvoAgent.genesis).
        # Permite ao ImmuneMemoryExchange aplicar o gating de mesma-linhagem
        # mesmo para EvoAgents criados diretamente (fora do registry AgentBase).
        self._known_markers: Set[str] = set()

    def registrar_linhagem(self, marker: str) -> None:
        """Registra um lineage_marker como pertencente a este nó."""
        if marker:
            self._known_markers.add(marker)

    def owns_lineage(self, marker: str) -> bool:
        """Este nó possui (ou já viu) a linhagem informada?"""
        if marker in self._known_markers:
            return True
        try:
            from iaglobal.agents.agent_base import get_evo_registry

            return any(
                getattr(evo, "lineage_marker", "") == marker
                for evo in get_evo_registry().values()
            )
        except Exception:
            return False

    # ── serialização do ledger ──────────────────────────────────────────

    def _parse_patterns(self, conteudo: Optional[str]) -> List[Dict[str, Any]]:
        """Extrai a lista de vacinas do YAML/Markdown do ledger."""
        if not conteudo:
            return []
        try:
            corpo = conteudo.split("---", 2)[-1]  # descarta frontmatter
            for linha in corpo.splitlines():
                if linha.strip().startswith("vacinas:"):
                    bloco = linha.split("vacinas:", 1)[1].strip()
                    if bloco:
                        return json.loads(bloco)
        except Exception as e:  # ledger corrompido → trata como vazio
            logger.warning("[VACCINE-LEDGER] parse falhou (ignorado): %s", e)
        return []

    def _serialize(self, patterns: List[Dict[str, Any]], marker: str) -> str:
        """Monta o ledger Markdown com frontmatter + bloco de vacinas em JSON."""
        ts = datetime.now(UTC).isoformat()
        vacinas = json.dumps(
            sorted(patterns, key=lambda p: p.get("pattern", "")),
            ensure_ascii=False,
        )
        return (
            f"---\n"
            f'id: "linhagem_{marker}"\n'
            f'tipo: "VaccineLedger"\n'
            f'lineage_marker: "{marker}"\n'
            f'timestamp: "{ts}Z"\n'
            f'tags: ["#vacina", "#imunidade"]\n'
            f"---\n\n"
            f"# Vacinas da Linhagem {marker}\n\n"
            f"vacinas: {vacinas}\n"
        )

    # ── API pública ─────────────────────────────────────────────────────

    async def registrar_falha(
        self, evo: Any, pattern: str, context: Dict[str, Any]
    ) -> None:
        """
        Persiste um failure_pattern da linhagem no Obsidian e publica a vacina
        via ImmuneMemoryExchange (mesma linhagem).

        Dedupe por `pattern` — evita acúmulo tóxico de homocisteína repetida.
        """
        marker = evo.lineage_marker
        conteudo = await self._vault.ler_vacina(marker)
        padroes = self._parse_patterns(conteudo)

        if any(p.get("pattern") == pattern for p in padroes):
            return  # já imunizado contra este padrão

        padroes.append(
            {
                "pattern": pattern,
                "agent": evo.name,
                "context": {k: str(v)[:120] for k, v in (context or {}).items()},
            }
        )
        await self._vault.escrever_vacina(marker, self._serialize(padroes, marker))

        # Publica via ImmuneMemoryExchange (transporte entre nós da mesma linhagem)
        try:
            from iaglobal.immunity.immune_memory_exchange import immune_memory_exchange

            await immune_memory_exchange.publish_vaccine(marker, [pattern])
        except Exception as e:
            logger.debug("[VACCINE-LEDGER] publish_vaccine indisponível: %s", e)

    async def vacinas(self, lineage_marker: str) -> Set[str]:
        """Conjunto de padrões de vacina conhecidos para uma linhagem."""
        conteudo = await self._vault.ler_vacina(lineage_marker)
        return {
            p["pattern"] for p in self._parse_patterns(conteudo) if p.get("pattern")
        }

    async def aplicar_vacina(self, evo: Any) -> int:
        """
        Aplica as vacinas da linhagem ao EvoAgent (priming de memória imunológica).

        Só carrega padrões do PRÓPRIO lineage_marker → gating evolutivo: um agente
        nunca herda memória de linhagem estranha (evita autoimunidade arquitetural).
        """
        padroes = await self.vacinas(evo.lineage_marker)
        aplicadas = 0
        for p in padroes:
            if p not in evo._failure_patterns:
                evo._failure_patterns.append(p)
                aplicadas += 1
        if aplicadas:
            logger.info(
                "[VACCINE-LEDGER] %d vacina(s) aplicada(s) à linhagem %s",
                aplicadas,
                evo.lineage_marker,
            )
        return aplicadas


# Singleton — ponto único de cruzamento Obsidian × ImmuneMemoryExchange
vaccine_ledger = VaccineLedger()
