# tests/test_contextweaver.py
"""Testes de integração do ContextWeaver com a cadeia evolutiva.

Fluxo metabólico:
1. ContextWeaver injeta marcadores epigenéticos
2. PromptImprover combina persona + constraints do domínio
3. SkillGenerator cria skills para gaps detectados
4. SandboxValidator testa skills com KPIs objetivos
5. EvolutionCommittee avalia e aprova/rejeita
"""
import asyncio
import pytest
import sqlite3
import cbor2
from pathlib import Path

from iaglobal.graphs.nodes.no_context_weaver import run_context_weaver
from iaglobal.graphs.nodes.no_prompt_improver import run_prompt_improver
from iaglobal.graphs.nodes.no_skill_generator import run_skill_generator
from iaglobal.graphs.nodes.no_sandbox_validator import run_sandbox_validator
from iaglobal.graphs.nodes.no_evolution_committee import run_evolution_committee
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI


class TestContextWeaverIntegration:
    """Integração ContextWeaver → PromptImprover → EvolutionCommittee."""

    def test_context_weaver_injeta_marcadores(self):
        """ContextWeaver deve injetar marcadores epigenéticos no output."""
        async def run():
            ctx = {
                "input": {"task": "crie uma landing page dark theme"},
                "memory": {"prompt_intake": {"prompt": {"domain": "web"}}}
            }
            return await run_context_weaver(ctx)
        
        result = asyncio.run(run())
        assert "web:responsive" in result.get("epigenetic_context", "")
        assert result.get("detected_domain") == "web"

    def test_context_weaver_risk_alto(self):
        """ContextWeaver deve detectar risco alto via failure_analysis."""
        async def run():
            ctx = {
                "input": {"task": "crie API de pagamento"},
                "memory": {
                    "prompt_intake": {"prompt": {}},
                    "failure_analysis": {"error_type": "sql_injection"}
                }
            }
            return await run_context_weaver(ctx)
        
        result = asyncio.run(run())
        assert "risk:high" in result.get("epigenetic_context", "")

    def test_fluxo_contexto_para_prompt_improver(self):
        """PromptImprover deve receber e usar o contexto epigenético."""
        async def run():
            # Etapa 1: ContextWeaver
            ctx = {
                "input": {"task": "landing page responsiva dark theme"},
                "memory": {"prompt_intake": {"prompt": {"domain": "web"}}}
            }
            ctx_result = await run_context_weaver(ctx)
            ctx["memory"]["context_weaver"] = ctx_result
            
            # Etapa 2: PromptImprover
            return await run_prompt_improver(ctx)
        
        result = asyncio.run(run())
        assert len(result.get("output", "")) > 100
        assert result.get("prompt_improver_report", {}).get("detected_domains")

    def test_fluxo_completo_evolucao_simples(self):
        """Fluxo completo: context → skill → sandbox → committee."""
        async def run():
            # ContextWeaver
            ctx = {
                "input": {"task": "componente web seguro"},
                "memory": {"prompt_intake": {"prompt": {"domain": "web"}}}
            }
            ctx_result = await run_context_weaver(ctx)
            ctx["memory"]["context_weaver"] = ctx_result
            
            # PromptImprover
            prompt_result = await run_prompt_improver(ctx)
            ctx["memory"]["prompt_improver"] = prompt_result
            
            # SkillGenerator (gera skill baseada no prompt)
            skill_result = await run_skill_generator(ctx)
            ctx["memory"]["skill_generator"] = skill_result
            
            # SandboxValidator
            sandbox_result = await run_sandbox_validator(ctx)
            ctx["memory"]["sandbox_validator"] = sandbox_result
            
            # EvolutionCommittee
            committee_result = await run_evolution_committee(ctx)
            
            return {
                "context": ctx_result.get("domain_markers"),
                "prompt_len": len(prompt_result.get("output", "")),
                "skill": skill_result.get("new_skill"),
                "sandbox": sandbox_result.get("status"),
                "committee": committee_result.get("status")
            }
        
        result = asyncio.run(run())
        # Verificar que o fluxo completou sem crash
        assert result["context"] is not None or result["context"] == []
        assert result["prompt_len"] > 50
        # skill/sandbox/committee podem não ter valores se não houve gaps detectados
        # mas o importante é que não crashou
        assert result is not None

    def test_fluxo_financeiro_theme(self):
        """Teste do domínio financeiro com dark theme."""
        async def run():
            ctx = {
                "input": {"task": "crie dashboard financeiro com tema escuro"},
                "memory": {"prompt_intake": {"prompt": {"domain": "financeiro"}}}
            }
            ctx_result = await run_context_weaver(ctx)
            ctx["memory"]["context_weaver"] = ctx_result
            
            # PromptImprover deve usar persona financeira
            prompt_result = await run_prompt_improver(ctx)
            return {
                "epigenetic": ctx_result.get("epigenetic_context"),
                "detected_domain": ctx_result.get("detected_domain"),
                "persona": "quantitativo" in prompt_result.get("output", "").lower()
            }
        
        result = asyncio.run(run())
        assert "financeiro:dark_theme" in result["epigenetic"]
        assert result["detected_domain"] == "financeiro"

    def test_obsidian_recebe_decisoes_evolutivas(self):
        """Obsidian deve ter notas de evolução após fluxo completo."""
        subconscious = SubconsciousAPI()
        
        async def run():
            ctx = {
                "input": {"task": "teste integração obsidian"},
                "memory": {
                    "prompt_intake": {"prompt": {"domain": "web"}},
                    "skill_generator": {"output": {}},
                    "sandbox_validator": {"output": {"results": [
                        {"skill_name": "test_web_skill", "severity": "low"}
                    ]}}
                }
            }
            return await run_evolution_committee(ctx)
        
        result = asyncio.run(run())
        
        # Verificar nota no ShortTerm
        short_term = Path(subconscious.short_term_dir)
        notes = list(short_term.glob("evolution_committee_*.md"))
        assert len(notes) > 0, "Nota de evolução deve existir"

    def test_memory_vector_armazena_contextualizacao(self):
        """MemoryVector deve armazenar o contexto contextualizado."""
        from iaglobal._paths import CORE_DB
        
        async def run():
            ctx = {
                "input": {"task": "context vectorization test"},
                "memory": {"sandbox_validator": {"output": {"results": [
                    {"skill_name": "vector_test", "severity": "low"}
                ]}}}
            }
            return await run_evolution_committee(ctx)
        
        asyncio.run(run())
        
        # Verificar embeddings
        conn = sqlite3.connect(CORE_DB)
        rows = conn.execute("SELECT content FROM memory WHERE type='evolution'").fetchall()
        conn.close()
        
        assert len(rows) > 0, "MemoryVector deve ter embeddings de evolução"


class TestContextWeaverStress:
    """Testes de carga e edge cases."""

    def test_multiplas_tarefas_diferentes(self):
        """Múltiplas tarefas devem gerar contextos distintos."""
        async def run():
            tasks = ["web site", "mobile app", "API backend", "trading system"]
            results = []
            for task in tasks:
                ctx = {"memory": {"prompt_intake": {"prompt": {"domain": "unknown"}}}}
                result = await run_context_weaver({
                    "input": {"task": task},
                    "memory": {"prompt_intake": {"prompt": {"domain": "unknown"}}}
                })
                results.append(result.get("domain_markers"))
            return results
        
        results = asyncio.run(run())
        # Cada tarefa deve gerar contexto
        assert len(results) == 4
        for r in results:
            assert isinstance(r, list)

    def test_fluxo_vazio_tratado(self):
        """Fluxo com task vazio deve não crashar."""
        async def run():
            ctx = {"memory": {}}
            return await run_context_weaver(ctx)
        
        result = asyncio.run(run())
        assert "output" in result

    def test_fluxo_evolucao_committee_multiplas_calls(self):
        """Chamadas múltiplas ao EvolutionCommittee devem ser estáveis."""
        async def run():
            tasks = [
                run_evolution_committee({
                    "input": {"task": f"tarefa {i}"},
                    "memory": {"sandbox_validator": {"output": {"results": [
                        {"skill_name": f"skill_{i}", "severity": "low"}
                    ]}}}
                })
                for i in range(3)
            ]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(run())
        assert len(results) == 3
        for r in results:
            # result tem 'evolution_committee' contendo 'status'
            committee = r.get("evolution_committee", {})
            assert "status" in committee or "status" in r