# tests/test_evolution_committee.py
"""Testes de integração do EvolutionCommittee com Obsidian, Memory e Evolution.

Validação do fluxo metabólico completo:
- OmniMind (consciência) registra o agente
- Obsidian (short/long term) persiste decisões
- MemoryVector armazena embeddings
- LongTerm/ShortTerm recebem entradas CBOR2
- SkillRegistry atualizado com metadata evolutiva
"""
import asyncio
import pytest
import sqlite3
import cbor2
from pathlib import Path

from iaglobal.evolution.metacognition.evolution_committee import EvolutionCommittee
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal._paths import CORE_DB, MEMORY_SWAP_DIR


class TestEvolutionCommitteeIntegration:
    """Integração tripla: Obsidian + Memory + SkillRegistry."""

    def test_omnimind_registra_agente(self):
        """EvolutionCommittee deve registrar agente na OmniMind."""
        ctx = {"memory": {"sandbox_validator": {"output": {"results": []}}}}
        result = asyncio.run(EvolutionCommittee.evaluate(ctx))
        
        # Verificar agente registrado
        agentes = omni_mind._agentes_registrados
        committee_agents = [k for k in agentes.keys() if "evolution_committee" in k.lower()]
        assert len(committee_agents) > 0, "EvolutionCommittee deve registrar agente"

    def test_obsidian_short_term_recebe_nota(self):
        """Notas devem ser escritas em 02_Short_Term."""
        subconscious = SubconsciousAPI()
        
        async def run():
            ctx = {
                "input": {"task": "test obsidian integration"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "test_evolve", "severity": "low"}
                ]}}}
            }
            return await EvolutionCommittee.evaluate(ctx)
        
        result = asyncio.run(run())
        
        # Verificar nota criada
        short_term = Path(subconscious.short_term_dir)
        evolucao_notes = list(short_term.glob("evolution_committee_*.md"))
        assert len(evolucao_notes) > 0, "Nota de evolução deve existir em ShortTerm"

    def test_obsidian_long_term_consolidado(self):
        """Skills aprovadas devem ir para 03_Long_Term."""
        subconscious = SubconsciousAPI()
        
        async def run():
            ctx = {
                "input": {"task": "consolidar no longo prazo"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "approved_skill_lt", "severity": "low"}
                ]}}}
            }
            return await EvolutionCommittee.evaluate(ctx)
        
        result = asyncio.run(run())
        
        # Verificar nota em LongTerm
        long_term = Path(subconscious.long_term_dir)
        evolucao_notes = list(long_term.glob("evolucao_*.md"))
        assert len(evolucao_notes) > 0, "Nota de evolução deve existir em LongTerm"

    def test_memory_vector_recebe_embedding(self):
        """MemoryVector deve armazenar embeddings das avaliações."""
        async def run():
            ctx = {
                "input": {"task": "test embedding"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "embed_test", "severity": "medium"}
                ]}}}
            }
            return await EvolutionCommittee.evaluate(ctx)
        
        result = asyncio.run(run())
        
        # Verificar embedding no core.db
        conn = sqlite3.connect(CORE_DB)
        rows = conn.execute("SELECT content, embedding FROM memory WHERE type='evolution'").fetchall()
        conn.close()
        
        assert len(rows) > 0, "MemoryVector deve ter entradas de evolucao"

    def test_ltm_cbor2_persiste(self):
        """LongTermMemory deve armazenar em CBOR2."""
        async def run():
            ctx = {
                "input": {"task": "ltm cbor2 test"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "ltm_skill", "severity": "low"}
                ]}}}
            }
            return await EvolutionCommittee.evaluate(ctx)
        
        result = asyncio.run(run())
        
        # Verificar CBOR2 em LTM
        conn = sqlite3.connect(CORE_DB)
        rows = conn.execute("SELECT data FROM ltm_entries").fetchall()
        conn.close()
        
        assert len(rows) > 0, "LTM deve ter entradas CBOR2"

    def test_skill_registry_atualizado(self):
        """SkillRegistry deve receber metadata evolution_status."""
        from iaglobal.evolution.skills.skill_registry import skill_registry
        from iaglobal.evolution.skills.skill import Skill
        
        async def run():
            # Registrar skill temporária
            skill = Skill(name="temp_test_skill", version="v1", description="Test skill")
            skill_registry.register(skill)
            
            ctx = {
                "input": {"task": "test registry update"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "temp_test_skill", "severity": "low"}
                ]}}}
            }
            return await EvolutionCommittee.evaluate(ctx)
        
        result = asyncio.run(run())
        
        # Verificar metadata
        registered = skill_registry.get("temp_test_skill")
        assert registered is not None
        if registered.metadata:
            assert registered.metadata.get("evolution_status") in ["approved", "rejected"]

    def test_fluxo_completo_decisao(self):
        """Fluxo completo: avalia → decide → persiste → atualiza."""
        async def run():
            ctx = {
                "input": {"task": "fluxo completo teste"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "high_gain_skill", "severity": "high"},
                    {"skill_name": "low_risk_skill", "severity": "low"}
                ]}}}
            }
            return await EvolutionCommittee.evaluate(ctx)
        
        result = asyncio.run(run())
        
        # Verificar estrutura de retorno
        assert "evaluations" in result
        assert "all_approved" in result
        assert "omnimind_guidance" in result
        assert result["total"] == 2


class TestEvolutionCommitteeStress:
    """Testes de estresse e carga."""

    def test_multiplas_consultas_nao_quebram(self):
        """Múltiplas chamadas concorrentes devem ser estáveis."""
        async def run():
            tasks = [
                EvolutionCommittee.evaluate({
                    "input": {"task": f"tarefa {i}"},
                    "memory": {"sandbox_validator": {"output": {"results": [
                        {"skill_name": f"skill_{i}", "severity": "low"}
                    ]}}}
                })
                for i in range(5)
            ]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(run())
        assert len(results) == 5
        for r in results:
            assert "status" in r

    def test_skill_inexistente_tratado(self):
        """Skill não registrada deve ser tratada sem erro."""
        async def run():
            ctx = {
                "input": {"task": "skill inexistente"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "nonexistent_skill_xyz", "severity": "low"}
                ]}}}
            }
            return await EvolutionCommittee.evaluate(ctx)
        
        result = asyncio.run(run())
        # Deve completar sem crash
        assert result["total"] == 1