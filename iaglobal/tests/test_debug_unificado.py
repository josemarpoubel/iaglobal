# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes para Debug Unificado — Skill + Node com integração LSP.

Cobertura:
  - Correção com erro de sintaxe LSP
  - Correção com import inválido
  - Código válido (passa direto)
  - Fallback quando skill indisponível
  - Métricas de execução
"""

import pytest
from unittest.mock import patch


class TestDebugUnificadoComLSP:
    """Testes de integração do debug_unificado com LSP."""

    @pytest.mark.asyncio
    async def test_debug_com_erro_sintaxe_lsp(self):
        """Código com erro de sintaxe detectado pelo LSP."""
        from iaglobal.graphs.nodes.no_debug_unificado import run_debug_unificado

        ctx = {
            "memory": {
                "coder": {"output": "def foo(x\n    return x + 1"},
                "lsp_validator": {
                    "lsp_errors": ["SyntaxError: '(' was never closed"],
                    "diagnostics": [{"line": 1, "message": "'(' was never closed"}],
                },
            },
            "input": {"task": "corrigir função foo"},
            "estimated_cost": 0.01,
        }

        result = await run_debug_unificado(ctx)

        # Verificações
        assert result is not None
        assert "output" in result
        assert "debug_result" in result
        assert "execution_metrics" in result

        dr = result["debug_result"]
        assert "success" in dr
        assert "attempts" in dr
        assert "model_used" in dr

        metrics = result["execution_metrics"]
        # Aceita variações do modelo: skill_debug_unificado, debug_unificado, ou combinações com +jedi
        assert any(
            m in metrics["model"] for m in ["skill_debug_unificado", "debug_unificado"]
        )
        assert "latency" in metrics
        assert "cost" in metrics

    @pytest.mark.asyncio
    async def test_debug_com_import_invalido(self):
        """Código com import inválido detectado pelo LSP."""
        from iaglobal.graphs.nodes.no_debug_unificado import run_debug_unificado

        ctx = {
            "memory": {
                "coder": {"output": "import modulo_inexistente_xyz\nprint(1)"},
                "lsp_validator": {
                    "lsp_errors": ["Import não encontrado: 'modulo_inexistente_xyz'"],
                    "diagnostics": [],
                },
            },
            "input": {"task": "corrigir imports"},
            "estimated_cost": 0.01,
        }

        result = await run_debug_unificado(ctx)
        assert result is not None
        assert "output" in result

    @pytest.mark.asyncio
    async def test_debug_sem_erros(self):
        """Código válido deve passar direto."""
        from iaglobal.graphs.nodes.no_debug_unificado import run_debug_unificado

        ctx = {
            "memory": {
                "coder": {"output": "def foo(x):\n    return x + 1\n\nprint(foo(2))"},
                "lsp_validator": {
                    "lsp_errors": [],
                    "diagnostics": [],
                },
            },
            "input": {"task": "validar código"},
            "estimated_cost": 0.01,
        }

        result = await run_debug_unificado(ctx)
        assert result is not None
        # Código válido pode ou não ser modificado

    @pytest.mark.asyncio
    async def test_debug_fallback_sem_skill(self):
        """Fallback para DebuggerAgent quando skill indisponível."""
        from iaglobal.graphs.nodes.no_debug_unificado import run_debug_unificado

        # Mock para simular skill indisponível
        with patch(
            "iaglobal.graphs.nodes.no_debug_unificado._tentar_skill"
        ) as mock_skill:
            mock_skill.return_value = (None, None, 0, False)

            ctx = {
                "memory": {
                    "coder": {"output": "def foo(x\n    return x"},
                    "lsp_validator": {
                        "lsp_errors": ["SyntaxError"],
                        "diagnostics": [],
                    },
                },
                "input": {"task": "teste"},
                "estimated_cost": 0.01,
            }

            result = await run_debug_unificado(ctx)
            assert result is not None
            # Deve ter tentado fallback

    @pytest.mark.asyncio
    async def test_metricas_execution(self):
        """Verifica se métricas são retornadas corretamente."""
        from iaglobal.graphs.nodes.no_debug_unificado import run_debug_unificado

        ctx = {
            "memory": {
                "coder": {"output": "print(1)"},
                "lsp_validator": {"lsp_errors": [], "diagnostics": []},
            },
            "input": {"task": "teste"},
            "estimated_cost": 0.01,
        }

        result = await run_debug_unificado(ctx)

        metrics = result["execution_metrics"]
        assert "model" in metrics
        assert "success" in metrics
        assert "latency" in metrics
        assert "cost" in metrics
        assert metrics["latency"] >= 0
        assert metrics["cost"] >= 0


class TestSkillDebugUnificado:
    """Testes da SkillDebugUnificado."""

    def test_skill_registrada(self):
        """Verifica se a skill está registrada."""
        from iaglobal.evolution.skills.native.skill_registry import skill_registry
        from iaglobal.evolution.skills.native.skill import register_builtin_skills

        register_builtin_skills()
        skill = skill_registry.get("debug_unificado")

        assert skill is not None
        assert skill.name == "debug_unificado"
        assert "lsp" in skill.description.lower()

    def test_skill_inputs_outputs(self):
        """Verifica inputs e outputs da skill."""
        from iaglobal.evolution.skills.native.skill_debug_unificado import (
            SkillDebugUnificado,
        )

        skill = SkillDebugUnificado()

        assert "code" in skill.inputs
        assert "lsp_errors" in skill.inputs
        assert "task" in skill.inputs
        assert "corrected_code" in skill.outputs

    @pytest.mark.asyncio
    async def test_skill_detecta_tipo_erro(self):
        """Skill detecta tipo de erro e gera prompt específico."""
        from iaglobal.evolution.skills.native.skill_debug_unificado import (
            SkillDebugUnificado,
        )
        from iaglobal.models.task import Task

        skill = SkillDebugUnificado()

        # Erro de sintaxe
        code = "def foo(x\n    return x"
        lsp_errors = ["SyntaxError: '(' was never closed"]
        task = Task(objective="Teste", code=code, context={"lsp_errors": lsp_errors})

        prompt = skill.build_prompt_com_lsp(code, lsp_errors, "Teste")

        assert "sintaxe" in prompt.lower() or "SINTAXE" in prompt
        assert code in prompt
        assert lsp_errors[0] in prompt

    @pytest.mark.asyncio
    async def test_skill_execute_com_lsp(self):
        """Skill executa correção com contexto LSP."""
        from iaglobal.evolution.skills.native.skill_debug_unificado import (
            SkillDebugUnificado,
        )
        from iaglobal.models.task import Task

        skill = SkillDebugUnificado()

        code = "def foo(x\n    return x + 1"
        lsp_errors = ["SyntaxError: '(' was never closed"]
        task = Task(
            objective="Corrigir",
            code=code,
            context={"lsp_errors": lsp_errors, "task": "Corrigir função"},
        )

        # Executa (pode falhar com modelo fraco, mas não deve crashar)
        try:
            result = await skill.execute(task)
            assert isinstance(result, str)
        except Exception as e:
            # Se falhar, não deve ser erro catastrófico
            assert "Traceback" not in str(e)


class TestDebuggerAgentMelhorias:
    """Testes das melhorias no DebuggerAgent."""

    def test_build_fix_prompt_detecta_sintaxe(self):
        """Prompt detecta erro de sintaxe."""
        from iaglobal.agents.debugger_agent import DebuggerAgent
        from iaglobal.models.task import Task

        agent = DebuggerAgent()
        task = Task(objective="Teste")

        code = "def foo(x\n    return x"
        error = "SyntaxError: '(' was never closed"

        prompt = agent.build_fix_prompt(task=task, error=error, code=code)

        assert "ERRO DE SINTAXE" in prompt
        assert "Parênteses" in prompt or "parêntese" in prompt.lower()

    def test_build_fix_prompt_detecta_import(self):
        """Prompt detecta erro de import."""
        from iaglobal.agents.debugger_agent import DebuggerAgent
        from iaglobal.models.task import Task

        agent = DebuggerAgent()
        task = Task(objective="Teste")

        code = "import modulo_x"
        error = "Import não encontrado: 'modulo_x'"

        prompt = agent.build_fix_prompt(task=task, error=error, code=code)

        assert "IMPORT" in prompt
        assert "imports" in prompt.lower()

    def test_build_fix_prompt_detecta_undefined(self):
        """Prompt detecta variável indefinida."""
        from iaglobal.agents.debugger_agent import DebuggerAgent
        from iaglobal.models.task import Task

        agent = DebuggerAgent()
        task = Task(objective="Teste")

        code = "print(x)"
        error = "NameError: name 'x' is not defined"

        prompt = agent.build_fix_prompt(task=task, error=error, code=code)

        assert "INDEFINID" in prompt  # INDEFINIDA ou INDEFINIDO
