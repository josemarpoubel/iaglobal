import pytest

from iaglobal._paths import RESULTS_DIR
from iaglobal.security.ast_gateway import ASTGateway


class TestSkillExistence:
    """Testa se skills essenciais existem e estao registradas."""

    def test_skill_debug_unificado_registrada(self):
        """SkillDebugUnificado deve estar registrada no skill_registry."""
        from iaglobal.evolution.skills.native.skill_registry import skill_registry

        skill = skill_registry.get("debug_unificado")
        assert skill is not None, "Skill debug_unificado nao encontrada no registry"
        assert hasattr(skill, "execute")
        assert hasattr(skill, "name")
        assert skill.name == "debug_unificado"

    def test_skill_autocomplete_registrada(self):
        """SkillPythonAutocomplete deve estar registrada."""
        from iaglobal.evolution.skills.native.skill_registry import skill_registry

        skill = skill_registry.get("python_autocomplete")
        assert skill is not None, "Skill python_autocomplete nao encontrada"

    def test_skill_debug_usando_ast_gateway(self):
        """SkillDebugUnificado deve validar AST via ASTGateway."""
        from iaglobal.evolution.skills.native.skill_debug_unificado import (
            SkillDebugUnificado,
        )

        skill = SkillDebugUnificado()
        ast_gw = skill.debugger_agent.ast_gateway
        assert isinstance(ast_gw, ASTGateway)
        result = ast_gw.parse("def foo(): pass")
        assert result.valid
        result_erro = ast_gw.parse("def foo( pass")
        assert not result_erro.valid

    def test_debugger_agent_valida_com_ast_gateway(self):
        """DebuggerAgent._validate() usa ASTGateway, nao ast.parse direto."""
        from iaglobal.agents.debugger_agent import DebuggerAgent

        agent = DebuggerAgent(max_attempts=1)
        assert isinstance(agent.ast_gateway, ASTGateway)
        agent._validate("x = 1")
        with pytest.raises(ValueError):
            agent._validate("x = ")


class TestAgentCooperation:
    """Testa se agentes cooperam entre si na pipeline."""

    def _deps_chain(self, name):
        """Retorna todos os descendentes na chain de dependencias."""
        from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS

        skills = dict(PIPELINE_SKILLS)
        chain = set()
        visited = set()

        def walk(n):
            if n in visited:
                return
            visited.add(n)
            cfg = skills.get(n, {})
            for d in cfg.get("depends_on", []):
                chain.add(d)
                walk(d)

        walk(name)
        return chain

    def test_tester_na_cadeia_do_coder(self):
        """Coder deve estar na cadeia do tester (tester depende de qa → integrator → coder)."""
        chain = self._deps_chain("tester")
        assert "coder" in chain, "tester deve ter coder na cadeia de dependencias"

    def test_critic_na_cadeia_do_skill_generator(self):
        """Skill_generator deve ter critic na cadeia de dependencias."""
        chain = self._deps_chain("skill_generator")
        assert "critic" in chain, "skill_generator deve ter critic na cadeia"

    def test_reflexion_compartilha_cadeia_com_result_agent(self):
        """Reflexion e result_agent compartilham a mesma cadeia (retrospective)."""
        chain_r = self._deps_chain("result_agent")
        chain_x = self._deps_chain("reflexion")
        chain_t = self._deps_chain("tester")
        assert "retrospective" in chain_r
        assert "retrospective" in chain_x
        assert "tester" in chain_r
        assert "tester" in chain_x

    @pytest.mark.asyncio
    async def test_no_debug_unificado_contrato(self):
        """no_debug_unificado deve aceitar ctx e retornar dict com execution_metrics."""
        from iaglobal.graphs.nodes.no_debug_unificado import run_debug_unificado

        code = "def foo():\n    return 1\n"
        ctx = {
            "memory": {"coder": {"output": code}},
            "input": {"task": "teste"},
        }
        result = await run_debug_unificado(ctx)
        assert isinstance(result, dict)
        assert "output" in result
        assert "execution_metrics" in result
        assert "debug_result" in result

    @pytest.mark.asyncio
    async def test_no_tester_contrato(self):
        """no_tester deve aceitar ctx e retornar dict com execution_metrics."""
        from iaglobal.graphs.nodes.no_tester import run_tester

        code = "def soma(a, b): return a + b"
        ctx = {
            "memory": {"coder": {"output": code}},
            "input": {"task": "crie funcao soma"},
        }
        result = await run_tester(ctx)
        assert isinstance(result, dict)
        assert "output" in result
        assert "test_output" in result or "execution_metrics" in result

    @pytest.mark.asyncio
    async def test_no_reflexion_contrato(self):
        """no_reflexion deve aceitar ctx e retornar dict com execution_metrics."""
        from iaglobal.graphs.nodes.no_reflexion import run_reflexion

        code = "def soma(a, b): return a + b"
        ctx = {
            "memory": {"coder": {"output": code}},
            "input": {"task": "teste"},
        }
        result = await run_reflexion(ctx)
        assert isinstance(result, dict)
        assert "reflexion_analysis" in result or "output" in result
        assert "execution_metrics" in result

    @pytest.mark.asyncio
    async def test_result_agent_contrato(self):
        """no_result_agent deve aceitar ctx e retornar dict com execution_metrics."""
        from iaglobal.graphs.nodes.no_result_agent import run_result_agent

        ctx = {
            "input": {"task": "teste resultado"},
            "memory": {
                "coder": {"output": "def hello():\n    print('oi')\n"},
            },
        }
        result = await run_result_agent(ctx)
        assert isinstance(result, dict)
        assert "execution_metrics" in result
        final_file = result.get("final_file", "")
        if final_file:
            file_path = RESULTS_DIR / final_file
            assert file_path.exists() or not final_file

    def test_skill_generator_nao_crasha(self):
        """SkillGeneratorAgent deve rodar sem crash mesmo sem dados."""
        from iaglobal.agents.skill_generator_agent import SkillGeneratorAgent

        agent = SkillGeneratorAgent()
        skills = agent.analyze_and_generate()
        assert skills is not None


class TestPipelineOrdering:
    """Testa a ordenacao dos agentes via cadeia de dependencias."""

    def _order(self, a, b):
        """Verifica se 'a' esta antes de 'b' na pipeline via cadeia de dependecias de b."""
        from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS

        skills = dict(PIPELINE_SKILLS)
        chain = set()
        visited = set()

        def walk(n):
            if n in visited:
                return
            visited.add(n)
            cfg = skills.get(n, {})
            for d in cfg.get("depends_on", []):
                chain.add(d)
                walk(d)

        walk(b)
        return a in chain

    def test_tester_antes_de_critic(self):
        """tester esta na cadeia de dependencias do critic."""
        assert self._order("tester", "critic"), (
            "tester deve estar na cadeia de dependencias de critic"
        )

    def test_debug_unificado_antes_de_critic(self):
        """debug_unificado esta na cadeia de dependencias do critic."""
        assert self._order("debug_unificado", "critic"), (
            "debug_unificado deve estar na cadeia de critic"
        )

    def test_coder_antes_de_tester(self):
        """coder esta na cadeia de dependencias do tester."""
        assert self._order("coder", "tester"), "coder deve estar na cadeia de tester"

    def test_critic_antes_de_skill_generator(self):
        """critic esta na cadeia de dependencias do skill_generator."""
        assert self._order("critic", "skill_generator"), (
            "critic deve estar na cadeia de skill_generator"
        )

    def test_tester_antes_de_result_agent(self):
        """tester esta na cadeia de dependencias do result_agent."""
        assert self._order("tester", "result_agent"), (
            "tester deve estar na cadeia de result_agent"
        )
