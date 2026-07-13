# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# tests/test_lineage_proof.py

"""
Testes para o protocolo Lineage-Proof (Proof-of-Lineage via SHA3-512).

Protocolo: H_lineage = SHA3-512(G0 + Node_UID)
- G0 é mantido apenas em genesis/identity.py (RAM source)
- Cada nó carrega apenas seu node_uid efêmero
- O Tribunal valida por re-derivação local
"""

import hashlib
import pytest

GENESIS_HASH_OFFICIAL = (
    "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524"
    "f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"
)


# =====================================================================
# Helpers
# =====================================================================


def _g0_bytes() -> bytes:
    return bytes.fromhex(GENESIS_HASH_OFFICIAL)


def _derive(node_uid: str) -> str:
    return hashlib.sha3_512(_g0_bytes() + node_uid.encode()).hexdigest()


# =====================================================================
# Import do módulo sob teste
# =====================================================================

from iaglobal.graphs.nodes.no_lineage_proof import (
    generate_node_lineage,
    validate_batch,
    run_lineage_proof,
)


# =====================================================================
# Unit Tests — generate_node_lineage
# =====================================================================


class TestGenerateNodeLineage:
    def test_generates_sha3_512_hash(self):
        lineage_hash = generate_node_lineage("node-001")
        assert len(lineage_hash) == 128

    def test_hash_derived_from_g0_and_uid(self):
        uid = "node-001"
        lineage_hash = generate_node_lineage(uid)
        expected = _derive(uid)
        assert lineage_hash == expected

    def test_deterministic_for_same_uid(self):
        h1 = generate_node_lineage("node-abc")
        h2 = generate_node_lineage("node-abc")
        assert h1 == h2

    def test_different_uids_produce_different_hashes(self):
        h1 = generate_node_lineage("node-a")
        h2 = generate_node_lineage("node-b")
        assert h1 != h2

    def test_empty_uid_raises_value_error(self):
        with pytest.raises(ValueError):
            generate_node_lineage("")

    def test_non_string_uid_raises_value_error(self):
        with pytest.raises(ValueError):
            generate_node_lineage(123)

    def test_lineage_hash_is_hex_string(self):
        lineage_hash = generate_node_lineage("node-001")
        assert all(c in "0123456789abcdef" for c in lineage_hash)


# =====================================================================
# Unit Tests — validate_batch
# =====================================================================


class TestValidateBatch:
    def test_empty_batch_returns_valid(self):
        result = validate_batch([])
        assert result["valid"] is True
        assert result["sovereign_count"] == 0
        assert result["rejected"] == []

    def test_valid_batch_returns_valid(self):
        uids = ["node-1", "node-2", "node-3"]
        batch_manifest = [{"uid": uid, "lineage_hash": _derive(uid)} for uid in uids]
        result = validate_batch(batch_manifest, batch_id="batch-valid")
        assert result["valid"] is True
        assert result["sovereign_count"] == 3
        assert len(result["rejected"]) == 0

    def test_invalid_batch_returns_invalid(self):
        batch_manifest = [
            {"uid": "node-1", "lineage_hash": "a" * 128},
            {"uid": "node-2", "lineage_hash": "b" * 128},
        ]
        result = validate_batch(batch_manifest, batch_id="batch-invalid")
        assert result["valid"] is False
        assert result["sovereign_count"] == 0
        assert len(result["rejected"]) == 2

    def test_mixed_batch_partially_rejected(self):
        valid_uid = "node-valid"
        invalid_uid = "node-evil"
        batch_manifest = [
            {"uid": valid_uid, "lineage_hash": _derive(valid_uid)},
            {"uid": invalid_uid, "lineage_hash": "0" * 128},
        ]
        result = validate_batch(batch_manifest, batch_id="batch-mixed")
        assert result["valid"] is False
        assert result["sovereign_count"] == 1
        assert len(result["rejected"]) == 1
        assert result["rejected"][0]["uid"] == invalid_uid

    def test_missing_uid_in_entry(self):
        batch_manifest = [
            {"uid": "", "lineage_hash": _derive("node")},
        ]
        result = validate_batch(batch_manifest, batch_id="batch-missing")
        assert result["valid"] is False
        assert len(result["rejected"]) == 1
        assert (
            "uid ausente" in result["rejected"][0]["reason"].lower()
            or "uid" in result["rejected"][0]["reason"].lower()
        )

    def test_missing_lineage_hash_in_entry(self):
        batch_manifest = [
            {"uid": "node-1", "lineage_hash": ""},
        ]
        result = validate_batch(batch_manifest, batch_id="batch-missing-hash")
        assert result["valid"] is False
        assert len(result["rejected"]) == 1


# =====================================================================
# Async Tests — run_lineage_proof (single mode)
# =====================================================================


class TestRunLineageProofSingle:
    @pytest.mark.asyncio
    async def test_single_mode_returns_lineage_hash(self):
        ctx = {
            "node_uid": "node-single-001",
            "batch_id": "batch-single-001",
        }
        result = await run_lineage_proof(ctx)
        assert result["execution_metrics"]["success"] is True
        assert "lineage_hash" in result["lineage_proof"]
        assert result["lineage_proof"]["valid"] is True
        assert result["lineage_proof"]["lineage_hash"] == _derive(ctx["node_uid"])

    @pytest.mark.asyncio
    async def test_single_mode_execution_metrics(self):
        ctx = {
            "node_uid": "node-single-002",
            "batch_id": "batch-single-002",
        }
        result = await run_lineage_proof(ctx)
        metrics = result["execution_metrics"]
        assert metrics["model"] == "local_sha3_512"
        assert metrics["success"] is True
        assert metrics["cost"] == 0.0
        assert metrics["latency"] >= 0


# =====================================================================
# Async Tests — run_lineage_proof (batch mode)
# =====================================================================


class TestRunLineageProofBatch:
    @pytest.mark.asyncio
    async def test_batch_valid_returns_success(self):
        uids = ["batch-1", "batch-2"]
        batch_manifest = [{"uid": uid, "lineage_hash": _derive(uid)} for uid in uids]
        ctx = {
            "batch_manifest": batch_manifest,
            "batch_id": "batch-async-valid",
        }
        result = await run_lineage_proof(ctx)
        assert result["lineage_proof"]["valid"] is True
        assert result["lineage_proof"]["sovereign_count"] == 2
        assert result["execution_metrics"]["success"] is True

    @pytest.mark.asyncio
    async def test_batch_invalid_returns_failure(self):
        batch_manifest = [
            {"uid": "evil-1", "lineage_hash": "0" * 128},
        ]
        ctx = {
            "batch_manifest": batch_manifest,
            "batch_id": "batch-async-invalid",
        }
        result = await run_lineage_proof(ctx)
        assert result["lineage_proof"]["valid"] is False
        assert result["execution_metrics"]["success"] is False


# =====================================================================
# Async Tests — edge cases
# =====================================================================


class TestRunLineageProofEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_uid_returns_error(self):
        ctx = {"node_uid": ""}
        result = await run_lineage_proof(ctx)
        assert result["lineage_proof"]["valid"] is False
        assert result["execution_metrics"]["success"] is False


class TestRunLineageProofPipelineIntegration:
    """Novo modo padrão: integração automática no pipeline."""

    @pytest.mark.asyncio
    async def test_empty_context_triggers_pipeline_integration(self):
        ctx = {}
        result = await run_lineage_proof(ctx)
        assert result["execution_metrics"]["success"] is True
        assert "output" in result
        assert "total" in result["output"]

    @pytest.mark.asyncio
    async def test_none_node_uid_triggers_pipeline_integration(self):
        ctx = {"node_uid": None}
        result = await run_lineage_proof(ctx)
        assert result["execution_metrics"]["success"] is True
        assert "output" in result
        assert "total" in result["output"]

    @pytest.mark.asyncio
    async def test_pipeline_integration_returns_total_count(self):
        ctx = {}
        result = await run_lineage_proof(ctx)
        output = result["output"]
        assert "total" in output
        assert output["total"] >= 0


# =====================================================================
# Security Tests
# =====================================================================


class TestLineageProofSecurity:
    def test_hash_changes_with_g0(self):
        """If G0 changes, all lineage hashes become invalid."""
        fake_g0 = bytes.fromhex("a" * 128)
        uid = "node-secure"
        expected_with_real_g0 = _derive(uid)
        expected_with_fake_g0 = hashlib.sha3_512(fake_g0 + uid.encode()).hexdigest()
        assert expected_with_real_g0 != expected_with_fake_g0

    def test_hash_changes_with_uid(self):
        """Different UIDs produce different hashes."""
        h1 = _derive("node-a")
        h2 = _derive("node-b")
        assert h1 != h2

    def test_no_genesis_carry_in_node_output(self):
        """The node output should not contain GENESIS_HASH_OFFICIAL."""
        lineage_hash = generate_node_lineage("node-safe")
        assert lineage_hash != GENESIS_HASH_OFFICIAL
        assert len(lineage_hash) == 128
