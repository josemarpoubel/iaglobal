# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes para integração do ContaminationReport no pipeline.

Cobertura:
  - claim_detection.py (fonte única de detecção)
  - ArtifactWriter usa módulo centralizado
  - REMSleep usa módulo centralizado
  - Reports são gerados automaticamente
"""
import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from iaglobal.reflection.contamination_report import ContaminationReport, report_architectural_hallucination
from iaglobal.reflection.claim_detection import (
    detect_architectural_claims,
    verify_architectural_claims,
    create_quarantine_report,
)
from iaglobal.obsidian.consolidation import REMSleepEngine


class TestContaminationReport:
    """Testes para ContaminationReport."""

    def test_create_report(self, tmp_path):
        """Testa criação de relatório de contaminação."""
        report = ContaminationReport()
        report.report_dir = tmp_path
        
        report_path = report.create_report(
            artifact_path="/fake/path.md",
            contamination_type="architectural_hallucination",
            llm_model="qwen2.5:0.5b",
            false_claims=["sistema não tem busca web"],
            verified_facts={"nodes": ["no_search.py"]},
            action_taken="removed_before_rem_cycle",
        )
        
        assert report_path.exists()
        assert "contamination" in report_path.name

    def test_report_architectural_hallucination(self, tmp_path):
        """Testa função helper de report."""
        report = ContaminationReport()
        report.report_dir = tmp_path
        
        report_path = report.create_report(
            artifact_path="/fake/path.md",
            contamination_type="architectural_hallucination",
            llm_model="qwen2.5:0.5b",
            false_claims=["iaglobal não tem search"],
            verified_facts={"nodes": ["search"]},
            action_taken="removed",
        )
        
        assert report_path.exists()


class TestClaimDetectionCentralized:
    """Testes para módulo centralizado claim_detection.py."""

    def test_detect_architectural_claims(self):
        """Testa detecção de claims suspeitos."""
        text = """
        Este relatório afirma que iaglobal não possui mecanismo de busca na internet.
        O sistema é auto-contido e offline-first.
        Não há WebSearchAgent ou SearchNode implementado.
        """
        
        claims = detect_architectural_claims(text)
        
        assert len(claims) > 0
        assert any("false_negative_capability" in c["type"] for c in claims)
        assert any("architectural_hallucination" in c["type"] for c in claims)

    def test_detect_no_claims_in_clean_text(self):
        """Testa que texto limpo não gera claims."""
        text = """
        Esta é uma função simples que soma dois números.
        Não há claims arquiteturais aqui.
        """
        
        claims = detect_architectural_claims(text)
        
        assert len(claims) == 0

    def test_verify_architectural_claims(self):
        """Testa verificação de claims contra código-fonte."""
        claims = [
            {"type": "false_negative_capability", "text": "iaglobal não tem search"},
        ]
        
        verified, unverified = verify_architectural_claims(claims)
        
        # no_search.py existe, então claim é falso
        assert verified == False
        assert len(unverified) > 0

    def test_patterns_centralizados(self):
        """Testa que patterns são consistentes."""
        from iaglobal.reflection.claim_detection import ARCHITECTURAL_CLAIM_PATTERNS
        
        # Verifica que patterns incluem "|sistema"
        pattern_text = str(ARCHITECTURAL_CLAIM_PATTERNS)
        assert "sistema" in pattern_text
        
        # Verifica que todos os patterns têm tipo válido
        for pattern, claim_type in ARCHITECTURAL_CLAIM_PATTERNS:
            assert claim_type in ["false_negative_capability", "architectural_hallucination"]


class TestREMSleepQuarantine:
    """Testes para quarentena no REM Sleep."""

    @pytest.mark.asyncio
    async def test_quarantine_contaminated_memory(self, tmp_path):
        """Testa que memória contaminada vai para quarentena."""
        # Cria vault temporário
        vault = tmp_path / "vault"
        vault.mkdir()
        
        engine = REMSleepEngine(vault_path=vault)
        
        # Conteúdo contaminado
        conteudo = """
        iaglobal não possui busca web.
        O sistema é offline-first.
        """
        
        claims = detect_architectural_claims(conteudo)
        
        quarentena_path = await engine._mover_para_quarentena(
            arquivo="test.md",
            conteudo=conteudo,
            claims_suspeitos=claims,
        )
        
        assert quarentena_path.exists()
        assert "CONTAMINATED" in quarentena_path.name
        assert "AGUARDANDO_REVISAO_HUMANA" in quarentena_path.read_text()

    @pytest.mark.asyncio
    async def test_detect_claims_in_remsleep(self, tmp_path):
        """Testa detecção de claims no REM Sleep."""
        vault = tmp_path / "vault"
        vault.mkdir()
        
        engine = REMSleepEngine(vault_path=vault)
        
        texto_com_claims = "iaglobal não tem mecanismo de busca"
        claims = detect_architectural_claims(texto_com_claims)
        
        assert len(claims) > 0


class TestIntegration:
    """Testes de integração completa."""

    def test_full_contamination_workflow(self, tmp_path):
        """Testa fluxo completo: detecção → verificação → report → quarentena."""
        # 1. Detecta claims (módulo centralizado)
        texto = "iaglobal não possui busca na internet"
        claims = detect_architectural_claims(texto)
        
        assert len(claims) > 0
        
        # 2. Verifica claims (módulo centralizado)
        verified, unverified = verify_architectural_claims(claims)
        
        # 3. Cria quarentena (módulo centralizado)
        vault = tmp_path / "vault"
        vault.mkdir()
        
        quarentena_path = create_quarantine_report(
            arquivo="test.md",
            conteudo=texto,
            claims=claims,
            vault_path=vault,
        )
        
        assert quarentena_path.exists()
        
        # 4. Cria report JSON
        report = ContaminationReport()
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report.report_dir = report_dir
        
        report_path = report.create_report(
            artifact_path="/fake/path.md",
            contamination_type="architectural_hallucination",
            llm_model="qwen2.5:0.5b",
            false_claims=unverified if unverified else ["claim teste"],
            verified_facts={"nodes": ["search"]},
            action_taken="quarantined",
        )
        
        assert report_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
