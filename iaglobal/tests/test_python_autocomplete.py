# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes para Skill Python Autocomplete com Jedi.

Cobertura:
  - Análise estática de código válido
  - Detecção de erros de sintaxe
  - Detecção de imports inválidos
  - Sugestões de autocomplete
  - Integração com debug_unificado
"""
import pytest
import asyncio


class TestSkillPythonAutocomplete:
    """Testes da SkillPythonAutocomplete."""

    @pytest.mark.asyncio
    async def test_analise_codigo_valido(self):
        """Análise de código Python válido."""
        from iaglobal.evolution.skills.skill_python_autocomplete import SkillPythonAutocomplete
        from iaglobal.models.task import Task
        
        skill = SkillPythonAutocomplete()
        code = """
def foo(x):
    return x + 1

result = foo(2)
"""
        task = Task(objective='Analisar', code=code)
        result = await skill.execute(task)
        
        assert result is not None
        assert 'suggestions' in result
        assert 'analysis' in result
        assert 'corrected_code' in result
        
        analysis = result['analysis']
        assert analysis.get('has_syntax_error') == False
        assert len(analysis.get('symbols', [])) > 0

    @pytest.mark.asyncio
    async def test_detecta_erro_sintaxe(self):
        """Detecta erro de sintaxe com Jedi + pyflakes."""
        from iaglobal.evolution.skills.skill_python_autocomplete import SkillPythonAutocomplete
        from iaglobal.models.task import Task
        
        skill = SkillPythonAutocomplete()
        code = 'def foo(x\n    return x'
        
        task = Task(objective='Analisar erro', code=code)
        result = await skill.execute(task)
        
        analysis = result['analysis']
        assert analysis.get('has_syntax_error') == True
        assert len(analysis.get('issues', [])) > 0
        
        # Verifica se o erro foi detectado
        issues = analysis['issues']
        assert any('syntax' in str(i).lower() or "'('" in str(i) for i in issues)

    @pytest.mark.asyncio
    async def test_detecta_import_invalido(self):
        """Detecta import inválido."""
        from iaglobal.evolution.skills.skill_python_autocomplete import SkillPythonAutocomplete
        from iaglobal.models.task import Task
        
        skill = SkillPythonAutocomplete()
        code = 'import modulo_inexistente_xyz\nprint(1)'
        
        task = Task(objective='Analisar import', code=code)
        result = await skill.execute(task)
        
        analysis = result['analysis']
        issues = analysis.get('issues', [])
        
        # Pyflakes deve detectar import não utilizado ou módulo inexistente
        assert len(issues) > 0
        assert any('import' in str(i).lower() for i in issues)

    @pytest.mark.asyncio
    async def test_autocomplete_posicao(self):
        """Testa autocomplete em posição específica."""
        from iaglobal.evolution.skills.skill_python_autocomplete import SkillPythonAutocomplete
        from iaglobal.models.task import Task
        
        skill = SkillPythonAutocomplete()
        code = """
def foo(x):
    return x + 1

re
"""
        # Cursor na linha 5, coluna 2 (após 're')
        task = Task(
            objective='Autocomplete',
            code=code,
            context={'line': 5, 'column': 2},
        )
        result = await skill.execute(task)
        
        # Deve ter sugestões
        assert 'suggestions' in result
        # Pode ou não ter sugestões dependendo do contexto
        # O importante é não crashar

    @pytest.mark.asyncio
    async def test_sugere_correcao_import(self):
        """Testa sugestão de correção para imports."""
        from iaglobal.evolution.skills.skill_python_autocomplete import SkillPythonAutocomplete
        from iaglobal.models.task import Task
        
        skill = SkillPythonAutocomplete()
        code = 'import modulo_x\nimport modulo_y\nprint(1)'
        
        task = Task(objective='Corrigir imports', code=code)
        result = await skill.execute(task)
        
        # Deve retornar código (original ou corrigido)
        assert 'corrected_code' in result
        assert isinstance(result['corrected_code'], str)

    @pytest.mark.asyncio
    async def test_type_hint_inferencia(self):
        """Testa inferência de tipos com Jedi."""
        from iaglobal.evolution.skills.skill_python_autocomplete import SkillPythonAutocomplete
        
        skill = SkillPythonAutocomplete()
        code = '''
def foo(x: int) -> int:
    return x + 1

result = foo(2)
'''
        # Testa método get_type_hint
        type_hint = skill.get_type_hint(code, 'foo')
        
        # Jedi deve inferir que foo é uma função
        assert type_hint is not None
        assert 'function' in type_hint.lower() or 'foo' in type_hint


class TestIntegracaoAutocompleteDebug:
    """Testes de integração entre autocomplete e debug_unificado."""

    @pytest.mark.asyncio
    async def test_debug_usa_autocomplete(self):
        """Debug unificado usa autocomplete para análise."""
        from iaglobal.graphs.nodes.no_debug_unificado import run_debug_unificado
        
        ctx = {
            'memory': {
                'coder': {'output': 'def foo(x):\n    return x + 1'},
                'lsp_validator': {
                    'lsp_errors': [],
                    'diagnostics': [],
                },
            },
            'input': {'task': 'analisar código'},
            'estimated_cost': 0.01,
        }
        
        result = await run_debug_unificado(ctx)
        
        # Deve retornar estrutura completa
        assert 'output' in result
        assert 'debug_result' in result
        assert 'execution_metrics' in result

    @pytest.mark.asyncio
    async def test_debug_com_jedi_analysis(self):
        """Debug com análise Jedi enriquece correção."""
        from iaglobal.evolution.skills.skill_registry import skill_registry
        from iaglobal.evolution.skills.skill import register_builtin_skills
        from iaglobal.models.task import Task
        
        # Registra skills
        register_builtin_skills()
        
        autocomplete = skill_registry.get('python_autocomplete')
        debug = skill_registry.get('debug_unificado')
        
        assert autocomplete is not None
        assert debug is not None
        
        # Testa fluxo integrado
        code = 'def foo(x):\n    return x + 1'
        
        # 1. Autocomplete analisa
        task_analise = Task(objective='Analisar', code=code)
        result_analise = await autocomplete.execute(task_analise)
        
        # 2. Debug usa análise
        task_debug = Task(
            objective='Corrigir',
            code=code,
            context={'jedi_analysis': result_analise['analysis']},
        )
        result_debug = await debug.execute(task_debug)
        
        assert result_debug is not None
        assert isinstance(result_debug, str)


class TestDebuggerAgentComJedi:
    """Testes do DebuggerAgent com integração Jedi."""

    def test_analyze_with_jedi(self):
        """DebuggerAgent analisa com Jedi."""
        from iaglobal.agents.debugger_agent import DebuggerAgent
        
        agent = DebuggerAgent()
        code = 'def foo(x):\n    return x + 1'
        error = ''
        
        # Testa método _analyze_with_jedi
        import asyncio
        analysis = asyncio.run(agent._analyze_with_jedi(code, error))
        
        assert 'issues' in analysis
        assert 'symbols' in analysis
        assert 'type_hints' in analysis
        assert 'available' in analysis
        assert analysis['available'] == True

    def test_build_fix_prompt_enhanced(self):
        """Prompt enriquecido com análise Jedi."""
        from iaglobal.agents.debugger_agent import DebuggerAgent
        from iaglobal.models.task import Task
        
        agent = DebuggerAgent()
        task = Task(objective='Teste')
        code = 'def foo(x):\n    return x'
        error = 'SyntaxError'
        jedi_analysis = {
            'available': True,
            'symbols': [{'name': 'foo', 'type': 'function'}],
            'type_hints': {},
        }
        
        prompt = agent.build_fix_prompt_enhanced(
            task=task,
            error=error,
            code=code,
            jedi_analysis=jedi_analysis,
        )
        
        # Prompt deve incluir análise base + info do Jedi
        assert len(prompt) > 100  # Prompt substancial
        assert 'ANÁLISE ESTÁTICA' in prompt or 'Jedi' in prompt or 'símbolos' in prompt.lower()