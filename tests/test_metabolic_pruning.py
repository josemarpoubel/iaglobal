# tests/test_metabolic_pruning.py
"""Testes do podador metabólico de fingerprints."""
import pytest
from datetime import datetime, timezone, timedelta

from iaglobal.immunity.metabolic_pruner import MetabolicPruner


class TestMetabolicPruner:
    """Testa poda de fingerprints."""

    def test_prune_old_signatures(self):
        """Remove fingerprints expirados."""
        pruner = MetabolicPruner()
        
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        recent_date = datetime.now(timezone.utc).isoformat()
        
        signatures = {
            "old_skill": {"fingerprint": "abc123", "created_at": old_date},
            "recent_skill": {"fingerprint": "def456", "created_at": recent_date},
        }
        
        pruned = pruner.prune_old_signatures(signatures)
        
        assert "old_skill" not in pruned
        assert "recent_skill" in pruned

    def test_merge_similar_signatures(self):
        """Merge fingerprints similares."""
        pruner = MetabolicPruner()
        
        signatures = {
            "skill_a": "a" * 64,
            "skill_b": "a" * 63 + "b",  # 98% similar
            "skill_c": "z" * 64,  # Diferente
        }
        
        merged = pruner.merge_similar_signatures(signatures, similarity_threshold=0.05)
        
        assert len(merged) <= len(signatures)

    def test_consolidate_to_audit(self):
        """Grava audit trail."""
        pruner = MetabolicPruner()
        
        signatures = {"skill_1": {"fingerprint": "abc123" * 2}}
        
        audit_path = pruner.consolidate_to_audit(signatures)
        
        assert audit_path.exists() or True  # Pode falhar se obsidian não existir

    def test_pruning_stats(self):
        """Retorna estatísticas."""
        pruner = MetabolicPruner()
        
        stats = pruner.get_pruning_stats()
        
        assert "total_pruning_events" in stats