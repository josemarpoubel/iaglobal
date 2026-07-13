# ============================================================
# ARQUIVO: iaglobal/obsidian/ancestry_tree.py
# ÁRVORE DE ANCESTRALIDADE: "A herança genética deve preservar..."
# ============================================================
"""AncestryTree — Rastreio de Linhagem e Mutações no Obsidian.

A Lei da Replicação estabelece que a herança genética deve preservar
a identidade da linhagem. Este módulo implementa:

1. **Registro de Linhagem** — Grava fusões no vault do Obsidian
2. **Árvore Visual** — Gera MOC (Map of Content) da linhagem
3. **Rastreio de Mutações** — Monitora mudanças de traits entre gerações
4. **DNA Timeline** — Linha do tempo evolutiva do ecossistema

Operação:
- Intercepta fusões do FusionEngine
- Cria notas no Obsidian para cada híbrido
- Gera links entre pais e filhos
- Atualiza MOC de ancestralidade
- Rastreia mutações de traits entre gerações

Padrão Singleton — existe um único AncestryTree para todo o ecossistema.

Exemplo de uso assíncrono:
    ```python
    from iaglobal.obsidian.ancestry_tree import ancestry_tree

    # Registrar fusão no Obsidian
    await ancestry_tree.register_fusion_async(
        hybrid_id="hybrid_001",
        parents=["coder_agent", "critic_agent"],
        resonance_score=0.85,
        traits_inherited={"coding_speed": "coder_agent", "detail": "critic_agent"},
    )

    # Gerar árvore visual de um híbrido
    tree_md = await ancestry_tree.generate_visual_tree_async("hybrid_001")

    # Obter timeline de mutações
    mutations = await ancestry_tree.get_mutation_timeline_async("hybrid_001")
    ```
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path

from iaglobal.utils.logger import get_logger
from iaglobal._paths import WORK_DIR

logger = get_logger("iaglobal.ancestry_tree")


@dataclass
class LineageNote:
    """Nota de linhagem no Obsidian."""

    note_id: str
    hybrid_id: str
    parents: List[str]
    generation: int
    resonance_score: float
    traits_inherited: Dict[str, str]
    mutations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())
    obsidian_path: Optional[str] = None


@dataclass
class MutationRecord:
    """Registro de uma mutação entre gerações."""

    mutation_id: str
    hybrid_id: str
    trait_name: str
    parent_value: Any
    hybrid_value: Any
    expression_change: float  # Diferença no expression_level
    impact_score: float  # 0.0 (neutra) → 1.0 (drástica)
    timestamp: float = field(default_factory=lambda: time.time())


class AncestryTree:
    """Árvore de Ancestralidade no Obsidian — Rastreio de Linhagem.

    A Lei da Replicação exige preservação da identidade da linhagem.
    Este módulo:

    1. Cria notas no Obsidian para cada fusão
    2. Gera links bidirecionais (pais ↔ filhos)
    3. Atualiza MOC (Map of Content) de ancestralidade
    4. Rastreia mutações de traits entre gerações
    5. Gera visualizações em Markdown da árvore

    Estrutura no Vault:
    ```
    iaglobal/obsidian/
    └── 05_Lineages/
        ├── MOC_Ancestry.md (índice de todas as linhagens)
        ├── hybrid_001.md
        ├── hybrid_002.md
        └── mutations/
            ├── mutation_001.md
            └── ...
    ```

    Padrão Singleton — existe um único AncestryTree para todo o ecossistema.
    """

    _instance: Optional["AncestryTree"] = None
    _lock = threading.Lock()

    # Configurações
    _OBSIDIAN_LINEAGES_DIR = WORK_DIR / "obsidian" / "05_Lineages"
    _OBSIDIAN_MUTATIONS_DIR = _OBSIDIAN_LINEAGES_DIR / "mutations"
    _MOC_FILE = _OBSIDIAN_LINEAGES_DIR / "MOC_Ancestry.md"

    def __new__(cls, *args, **kwargs) -> "AncestryTree":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._lineage_notes: Dict[str, LineageNote] = {}
        self._mutation_records: List[MutationRecord] = []
        self._rlock = threading.RLock()
        self._ensured_dirs = False

        logger.info(
            "[AncestryTree] Árvore de Ancestralidade initialized | lineages_dir=%s",
            self._OBSIDIAN_LINEAGES_DIR,
        )

    def _ensure_structure(self) -> None:
        """Garante que diretórios do Obsidian existem."""
        if self._ensured_dirs:
            return

        with self._rlock:
            self._OBSIDIAN_LINEAGES_DIR.mkdir(parents=True, exist_ok=True)
            self._OBSIDIAN_MUTATIONS_DIR.mkdir(parents=True, exist_ok=True)

            # Criar MOC inicial se não existe
            if not self._MOC_FILE.exists():
                self._MOC_FILE.write_text(self._generate_moc_template())

            self._ensured_dirs = True
            logger.debug("[AncestryTree] Estrutura do Obsidian garantida")

    def _generate_moc_template(self) -> str:
        """Gera template do MOC de Ancestralidade."""
        now = datetime.now(timezone.utc).isoformat()
        return f"""# 🧬 AncestryTree — Mapa de Linhagens

**Última Atualização**: {now}

## 📊 Estatísticas

- **Total de Híbridos**: 0
- **Geração Atual**: 0
- **Mutações Rastreadas**: 0

## 🌳 Linhagens

<!-- Linhagens serão inseridas aqui -->

## 🧬 Mutações Notáveis

<!-- Mutações serão inseridas aqui -->

---

*Gerado automaticamente por AncestryTree — Lei da Replicação*
"""

    async def register_fusion_async(
        self,
        hybrid_id: str,
        parents: List[str],
        resonance_score: float,
        traits_inherited: Dict[str, str],
        generation: int = 1,
        obsidian_note_id: Optional[str] = None,
    ) -> LineageNote:
        """
        Registra fusão no Obsidian.

        Args:
            hybrid_id: ID do agente híbrido
            parents: Lista de IDs dos pais
            resonance_score: Score de ressonância da fusão
            traits_inherited: Mapeamento trait → parent_id
            generation: Geração do híbrido
            obsidian_note_id: ID da nota (opcional)

        Returns:
            LineageNote: Nota criada
        """
        await asyncio.to_thread(self._ensure_structure)

        now = time.time()

        # Detectar mutações
        mutations = await asyncio.to_thread(
            self._detect_mutations,
            hybrid_id,
            parents,
            traits_inherited,
        )

        # Criar nota
        note = LineageNote(
            note_id=obsidian_note_id or f"lineage_{hybrid_id}_{int(now)}",
            hybrid_id=hybrid_id,
            parents=parents,
            generation=generation,
            resonance_score=resonance_score,
            traits_inherited=traits_inherited,
            mutations=mutations,
            created_at=now,
        )

        with self._rlock:
            self._lineage_notes[hybrid_id] = note
            self._mutation_records.extend(mutations)

        # Escrever nota no Obsidian
        note_path = await asyncio.to_thread(
            self._write_lineage_note,
            note,
        )
        note.obsidian_path = str(note_path)

        # Atualizar MOC
        await asyncio.to_thread(self._update_moc)

        logger.info(
            "[AncestryTree] ✅ Linhagem registrada: %s (gen=%d, pais=%d, mutações=%d)",
            hybrid_id,
            generation,
            len(parents),
            len(mutations),
        )

        return note

    def _detect_mutations(
        self,
        hybrid_id: str,
        parents: List[str],
        traits_inherited: Dict[str, str],
    ) -> List[MutationRecord]:
        """Detecta mutações reais comparando DNA dos pais com o híbrido."""
        mutations = []

        for trait_name, parent_id in traits_inherited.items():
            mutation_id = hashlib.sha3_256(
                f"{hybrid_id}:{trait_name}:{time.time()}".encode()
            ).hexdigest()[:16]

            parent_value = self._get_parent_trait_value(parent_id, trait_name)
            hybrid_value = self._get_hybrid_trait_value(hybrid_id, trait_name)

            expression_change = self._calculate_expression_change(
                parent_value, hybrid_value
            )
            impact_score = self._calculate_impact_score(
                parent_value, hybrid_value, expression_change
            )

            mutation = MutationRecord(
                mutation_id=mutation_id,
                hybrid_id=hybrid_id,
                trait_name=trait_name,
                parent_value=parent_value,
                hybrid_value=hybrid_value,
                expression_change=expression_change,
                impact_score=impact_score,
            )
            mutations.append(mutation)

        return mutations

    def _get_parent_trait_value(self, parent_id: str, trait_name: str) -> str:
        """Obtém valor do trait do pai a partir do registro de linhagem."""
        parent_note = self._lineage_notes.get(parent_id)
        if parent_note and trait_name in parent_note.traits_inherited:
            return f"{trait_name}={parent_note.traits_inherited[trait_name]}"
        return "unknown"

    def _get_hybrid_trait_value(self, hybrid_id: str, trait_name: str) -> str:
        """Obtém valor do trait do híbrido (simulado - em produção viria do DNA real)."""
        return f"{trait_name}_evolved"

    def _calculate_expression_change(
        self, parent_value: str, hybrid_value: str
    ) -> float:
        """Calcula mudança na expressão do trait."""
        if parent_value == "unknown" or hybrid_value == "unknown":
            return 0.1
        if parent_value == hybrid_value:
            return 0.0
        return 0.5

    def _calculate_impact_score(
        self, parent_value: str, hybrid_value: str, expression_change: float
    ) -> float:
        """Calcula score de impacto da mutação."""
        base_score = 0.3
        if expression_change > 0:
            base_score += expression_change * 0.5
        if parent_value != hybrid_value:
            base_score += 0.2
        return min(1.0, base_score)

    def _write_lineage_note(self, note: LineageNote) -> Path:
        """Escreve nota de linhagem no Obsidian."""
        timestamp = datetime.fromtimestamp(note.created_at, timezone.utc).isoformat()

        # Formatar pais com links
        parents_md = ", ".join(f"[[{p}]]" for p in note.parents)

        # Formatar traits herdadas
        traits_table = "| Trait | Herdado de |\n|-------|------------|\n"
        for trait, parent in note.traits_inherited.items():
            traits_table += f"| `{trait}` | [[{parent}]] |\n"

        # Formatar mutações
        mutations_section = ""
        if note.mutations:
            mutations_section = "\n## 🧬 Mutações Detectadas\n\n"
            for mut in note.mutations:
                mutations_section += (
                    f"- **{mut.trait_name}**: "
                    f"impact={mut.impact_score:.2f}, "
                    f"expressão={mut.expression_change:+.2f}\n"
                )

        content = f"""# 🧬 Linhagem: {note.hybrid_id}

**Geração**: {note.generation}  
**Ressonância**: {note.resonance_score:.2f}  
**Criado em**: {timestamp}

## 👨‍👩‍👧‍👦 Pais

{parents_md}

## 🧬 Traits Herdadas

{traits_table}
{mutations_section}
## 🔗 Links

- [[MOC_Ancestry|Voltar ao Mapa de Linhagens]]
"""

        note_path = self._OBSIDIAN_LINEAGES_DIR / f"{note.hybrid_id}.md"
        note_path.write_text(content)

        return note_path

    def _update_moc(self) -> None:
        """Atualiza MOC de Ancestralidade."""
        with self._rlock:
            total_hybrids = len(self._lineage_notes)
            max_generation = max(
                (n.generation for n in self._lineage_notes.values()),
                default=0,
            )
            total_mutations = len(self._mutation_records)

            # Gerar lista de linhagens
            lineages_list = ""
            for note in sorted(
                self._lineage_notes.values(),
                key=lambda n: n.generation,
            ):
                parents_str = ", ".join(note.parents)
                lineages_list += (
                    f"- **[[{note.hybrid_id}]]** "
                    f"(gen {note.generation}, ressonância={note.resonance_score:.2f})\n"
                    f"  - Pais: {parents_str}\n"
                )

            # Gerar lista de mutações notáveis
            mutations_list = ""
            if self._mutation_records:
                top_mutations = sorted(
                    self._mutation_records,
                    key=lambda m: m.impact_score,
                    reverse=True,
                )[:5]

                mutations_list = "\n".join(
                    f"- **{m.mutation_id}**: {m.trait_name} "
                    f"(impact={m.impact_score:.2f})"
                    for m in top_mutations
                )

            timestamp = datetime.now(timezone.utc).isoformat()

            content = f"""# 🧬 AncestryTree — Mapa de Linhagens

**Última Atualização**: {timestamp}

## 📊 Estatísticas

- **Total de Híbridos**: {total_hybrids}
- **Geração Atual**: {max_generation}
- **Mutações Rastreadas**: {total_mutations}

## 🌳 Linhagens

{lineages_list}

## 🧬 Mutações Notáveis

{mutations_list if mutations_list else "*Nenhuma mutação registrada ainda*"}

---

*Gerado automaticamente por AncestryTree — Lei da Replicação*
"""

            self._MOC_FILE.write_text(content)

    async def generate_visual_tree_async(
        self,
        hybrid_id: str,
        depth: int = 3,
    ) -> str:
        """
        Gera árvore visual em Markdown para um híbrido.

        Args:
            hybrid_id: ID do híbrido
            depth: Profundidade máxima da árvore

        Returns:
            str: Árvore em formato Markdown
        """
        note = self._lineage_notes.get(hybrid_id)
        if not note:
            return f"❌ Linhagem não encontrada: {hybrid_id}"

        tree = await asyncio.to_thread(
            self._build_tree_recursive,
            hybrid_id,
            depth,
        )

        return tree

    def _build_tree_recursive(
        self,
        hybrid_id: str,
        depth: int,
        indent: str = "",
    ) -> str:
        """Constrói árvore recursivamente."""
        note = self._lineage_notes.get(hybrid_id)

        if not note:
            # Agente original (não híbrido)
            return f"{indent}- **{hybrid_id}** (original)\n"

        # Nó atual
        tree = (
            f"{indent}- **🧬 {hybrid_id}** "
            f"(gen {note.generation}, res={note.resonance_score:.2f})\n"
        )

        if depth > 1:
            # Filhos (na verdade, pais na árvore de ancestralidade)
            for parent_id in note.parents:
                tree += self._build_tree_recursive(
                    parent_id,
                    depth - 1,
                    indent + "  ",
                )

        return tree

    async def get_mutation_timeline_async(
        self,
        hybrid_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Retorna timeline de mutações para um híbrido.

        Args:
            hybrid_id: ID do híbrido

        Returns:
            Lista de mutações ordenadas por timestamp
        """
        with self._rlock:
            note = self._lineage_notes.get(hybrid_id)
            if not note:
                return []

            # Obter mutações deste híbrido
            mutations = [
                {
                    "mutation_id": m.mutation_id,
                    "trait_name": m.trait_name,
                    "impact_score": m.impact_score,
                    "expression_change": m.expression_change,
                    "timestamp": datetime.fromtimestamp(
                        m.timestamp, timezone.utc
                    ).isoformat(),
                }
                for m in self._mutation_records
                if m.hybrid_id == hybrid_id
            ]

            # Ordenar por timestamp
            mutations.sort(key=lambda x: x["timestamp"])

            return mutations

    def get_lineage_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de linhagens."""
        with self._rlock:
            if not self._lineage_notes:
                return {
                    "total_hybrids": 0,
                    "max_generation": 0,
                    "total_mutations": 0,
                    "avg_resonance": 0.0,
                }

            total = len(self._lineage_notes)
            max_gen = max(n.generation for n in self._lineage_notes.values())
            avg_res = (
                sum(n.resonance_score for n in self._lineage_notes.values()) / total
            )

            return {
                "total_hybrids": total,
                "max_generation": max_gen,
                "total_mutations": len(self._mutation_records),
                "avg_resonance": round(avg_res, 3),
                "hybrids_by_generation": self._count_by_generation(),
            }

    def _count_by_generation(self) -> Dict[int, int]:
        """Conta híbridos por geração."""
        counts = {}
        for note in self._lineage_notes.values():
            gen = note.generation
            counts[gen] = counts.get(gen, 0) + 1
        return counts

    def reset(self) -> None:
        """Reseta estado (para testes)."""
        with self._rlock:
            self._lineage_notes.clear()
            self._mutation_records.clear()
            logger.info("[AncestryTree] ✅ Estado resetado")


# Singleton global
ancestry_tree = AncestryTree()
