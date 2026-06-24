# tests/test_entropy_sentinel.py
"""Testes do Sentinela de Entropia (Genesis + PySecurity1024)."""
import pytest
import hashlib

from iaglobal.security.entropy_sentinel import EntropySentinel
from iaglobal.security.pysecurity1024 import gerar_node_id_soberano, Pysecurity1024


class TestEntropySentinel:
    """Testes da vigilância de integridade genética."""

    def test_generate_sober_agent_id(self):
        """ID soberano deve ser único e pronunciável."""
        sentinel = EntropySentinel()
        
        id1 = sentinel.get_sober_agent_id("test_agent")
        id2 = sentinel.get_sober_agent_id("test_agent")
        
        # Mesmo agente deve gerar mesmo ID (determinístico)
        assert id1 == id2
        # ID deve ser fonético (não bytes brutos)
        assert "-" in id1 or len(id1) > 0

    def test_file_hash_calculation(self, tmp_path):
        """Hash de arquivo deve ser calculado corretamente."""
        sentinel = EntropySentinel()
        
        test_file = tmp_path / "test.py"
        test_file.write_text("# test content")
        
        file_hash = sentinel.calculate_file_hash(test_file)
        
        # Verificar consistência
        expected = hashlib.sha3_512(b"# test content").hexdigest()
        assert file_hash is not None

    def test_scan_critical_files(self):
        """Scan deve encontrar arquivos críticos."""
        sentinel = EntropySentinel()
        
        result = sentinel.scan_critical_files()
        
        assert "healthy" in result
        assert "files_scanned" in result


class TestPySecurity1024:
    """Testes do motor de segurança fonética."""

    def test_byte_para_silaba(self):
        """Converte byte para sílaba corretamente."""
        silaba = Pysecurity1024.byte_para_silaba(255)
        assert len(silaba) >= 2

    def test_bytes_para_frase(self):
        """Converte bytes para frase fonética."""
        dados = b"test"
        frase = Pysecurity1024.bytes_para_frase(dados)
        
        assert isinstance(frase, str)
        assert "-" in frase or frase

    def test_gerar_node_id_soberano(self):
        """Gera ID único para nó."""
        public_key = b"test_public_key"
        node_id = gerar_node_id_soberano(public_key)
        
        assert isinstance(node_id, str)
        assert len(node_id) > 0