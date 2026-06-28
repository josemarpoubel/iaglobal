# tests/test_ancestry_tree.py
"""
Testes do AncestryTree — Rastreio de Linhagem no Obsidian.

Cobre:
- Registro de fusões
- Detecção de mutações
- Geração de árvore visual
- Timeline de mutações
- Estatísticas de linhagem
- Atualização de MOC
"""
import pytest
import asyncio
from pathlib import Path
from iaglobal.obsidian.ancestry_tree import (
    AncestryTree,
    ancestry_tree,
    LineageNote,
    MutationRecord,
)


class TestLineageRegistration:
    """Testes de registro de linhagem."""

    def setup_method(self):
        """Reset singleton antes de cada teste."""
        AncestryTree._instance = None

    @pytest.mark.asyncio
    async def test_register_fusion_creates_note(self):
        """Registro cria nota de linhagem."""
        tree = AncestryTree()
        
        note = await tree.register_fusion_async(
            hybrid_id="test_hybrid",
            parents=["parent_a", "parent_b"],
            resonance_score=0.85,
            traits_inherited={"trait1": "parent_a", "trait2": "parent_b"},
            generation=2,
        )
        
        assert note.hybrid_id == "test_hybrid"
        assert note.generation == 2
        assert len(note.parents) == 2
        assert note.resonance_score == 0.85
        assert note.obsidian_path is not None

    @pytest.mark.asyncio
    async def test_register_fusion_detects_mutations(self):
        """Registro detecta mutações automaticamente."""
        tree = AncestryTree()
        
        note = await tree.register_fusion_async(
            hybrid_id="mutant_hybrid",
            parents=["parent_a"],
            resonance_score=0.75,
            traits_inherited={"speed": "parent_a"},
        )
        
        assert len(note.mutations) > 0
        assert note.mutations[0].trait_name == "speed"

    @pytest.mark.asyncio
    async def test_register_fusion_ensures_structure(self, tmp_path):
        """Registro garante estrutura de diretórios."""
        tree = AncestryTree()
        tree._OBSIDIAN_LINEAGES_DIR = tmp_path / "obsidian" / "05_Lineages"
        tree._MOC_FILE = tree._OBSIDIAN_LINEAGES_DIR / "MOC_Ancestry.md"
        tree._ensured_dirs = False  # Forçar re-criação
        
        await tree.register_fusion_async(
            hybrid_id="test",
            parents=["parent"],
            resonance_score=0.8,
            traits_inherited={},
        )
        
        assert tree._OBSIDIAN_LINEAGES_DIR.exists()
        assert tree._MOC_FILE.exists()


class TestMutationDetection:
    """Testes de detecção de mutações."""

    def setup_method(self):
        AncestryTree._instance = None

    def test_detect_mutations_creates_records(self):
        """Detecção cria registros de mutação."""
        tree = AncestryTree()
        
        mutations = tree._detect_mutations(
            "hybrid_001",
            ["parent_a", "parent_b"],
            {"trait1": "parent_a", "trait2": "parent_b"},
        )
        
        assert len(mutations) == 2
        assert isinstance(mutations[0], MutationRecord)
        assert mutations[0].trait_name == "trait1"

    def test_mutation_record_has_unique_id(self):
        """Cada mutação tem ID único."""
        tree = AncestryTree()
        
        mutations = tree._detect_mutations(
            "hybrid_001",
            ["parent_a"],
            {"trait1": "parent_a"},
        )
        
        assert len(mutations[0].mutation_id) == 16  # SHA3-256[:16]


class TestVisualTree:
    """Testes de geração de árvore visual."""

    def setup_method(self):
        AncestryTree._instance = None

    @pytest.mark.asyncio
    async def test_generate_visual_tree(self):
        """Gera árvore em Markdown."""
        tree = AncestryTree()
        
        # Registrar híbrido e pais
        await tree.register_fusion_async(
            hybrid_id="hybrid_001",
            parents=["parent_a", "parent_b"],
            resonance_score=0.8,
            traits_inherited={},
            generation=2,
        )
        
        tree_md = await tree.generate_visual_tree_async("hybrid_001", depth=2)
        
        assert "🧬 hybrid_001" in tree_md
        assert "gen 2" in tree_md
        assert "parent_a" in tree_md or "parent_b" in tree_md

    @pytest.mark.asyncio
    async def test_generate_visual_tree_not_found(self):
        """Retorna erro se híbrido não existe."""
        tree = AncestryTree()
        
        tree_md = await tree.generate_visual_tree_async("nonexistent")
        
        assert "❌" in tree_md
        assert "não encontrada" in tree_md


class TestMutationTimeline:
    """Testes de timeline de mutações."""

    def setup_method(self):
        AncestryTree._instance = None

    @pytest.mark.asyncio
    async def test_get_mutation_timeline(self):
        """Retorna timeline de mutações."""
        tree = AncestryTree()
        
        await tree.register_fusion_async(
            hybrid_id="hybrid_001",
            parents=["parent_a"],
            resonance_score=0.8,
            traits_inherited={"speed": "parent_a"},
        )
        
        timeline = await tree.get_mutation_timeline_async("hybrid_001")
        
        assert len(timeline) > 0
        assert "mutation_id" in timeline[0]
        assert "trait_name" in timeline[0]
        assert "timestamp" in timeline[0]

    @pytest.mark.asyncio
    async def test_get_mutation_timeline_empty(self):
        """Retorna lista vazia se sem mutações."""
        tree = AncestryTree()
        
        timeline = await tree.get_mutation_timeline_async("nonexistent")
        
        assert timeline == []


class TestLineageStats:
    """Testes de estatísticas de linhagem."""

    def setup_method(self):
        AncestryTree._instance = None

    def test_get_lineage_stats(self):
        """Estatísticas incluem contagens e médias."""
        tree = AncestryTree()
        
        # Adicionar linhagens manualmente
        tree._lineage_notes["hybrid_001"] = LineageNote(
            note_id="n1",
            hybrid_id="hybrid_001",
            parents=["parent_a"],
            generation=2,
            resonance_score=0.8,
            traits_inherited={},
        )
        tree._lineage_notes["hybrid_002"] = LineageNote(
            note_id="n2",
            hybrid_id="hybrid_002",
            parents=["parent_b"],
            generation=3,
            resonance_score=0.9,
            traits_inherited={},
        )
        
        stats = tree.get_lineage_stats()
        
        assert stats["total_hybrids"] == 2
        assert stats["max_generation"] == 3
        assert stats["avg_resonance"] > 0.8
        assert "hybrids_by_generation" in stats

    def test_get_lineage_stats_empty(self):
        """Estatísticas vazias quando sem dados."""
        tree = AncestryTree()
        
        stats = tree.get_lineage_stats()
        
        assert stats["total_hybrids"] == 0
        assert stats["max_generation"] == 0
        assert stats["avg_resonance"] == 0.0


class TestMOCUpdate:
    """Testes de atualização do MOC."""

    def setup_method(self):
        AncestryTree._instance = None

    def test_update_moc_creates_file(self, tmp_path):
        """Atualização cria arquivo MOC."""
        tree = AncestryTree()
        tree._OBSIDIAN_LINEAGES_DIR = tmp_path / "lineages"
        tree._MOC_FILE = tree._OBSIDIAN_LINEAGES_DIR / "MOC.md"
        tree._ensured_dirs = True  # Pular ensure_structure
        
        # Garantir que diretório existe
        tree._OBSIDIAN_LINEAGES_DIR.mkdir(parents=True, exist_ok=True)
        
        tree._lineage_notes["hybrid_001"] = LineageNote(
            note_id="n1",
            hybrid_id="hybrid_001",
            parents=["parent_a"],
            generation=2,
            resonance_score=0.8,
            traits_inherited={},
        )
        
        tree._update_moc()
        
        assert tree._MOC_FILE.exists()
        content = tree._MOC_FILE.read_text()
        assert "hybrid_001" in content
        assert "Estatísticas" in content


class TestReset:
    """Testes de reset."""

    def setup_method(self):
        AncestryTree._instance = None

    def test_reset_clears_all(self):
        """Reset limpa todos os dados."""
        tree = AncestryTree()
        
        tree._lineage_notes["test"] = LineageNote(
            note_id="n",
            hybrid_id="test",
            parents=[],
            generation=1,
            resonance_score=0.5,
            traits_inherited={},
        )
        tree._mutation_records.append(MutationRecord(
            mutation_id="m1",
            hybrid_id="test",
            trait_name="trait",
            parent_value="a",
            hybrid_value="b",
            expression_change=0.1,
            impact_score=0.5,
        ))
        
        tree.reset()
        
        assert len(tree._lineage_notes) == 0
        assert len(tree._mutation_records) == 0


class TestSingleton:
    """Testes de singleton."""

    def test_singleton_instance(self):
        """AncestryTree é singleton."""
        AncestryTree._instance = None
        
        t1 = AncestryTree()
        t2 = AncestryTree()
        
        assert t1 is t2

    def test_global_singleton(self):
        """ancestry_tree global é instância válida."""
        assert isinstance(ancestry_tree, AncestryTree)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])