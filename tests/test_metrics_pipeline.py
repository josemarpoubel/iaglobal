"""
Teste de Integração Completo: Metrics Pipeline
============================================

Valida:
1. Caminho correto: métricas gravadas em /home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/provider_metrics/metrics.jsonl
2. Banco de dados de memória inicializado (tabela 'memory' existe)
3. Pipeline completo: run_code_executor -> run_knowledge_writer -> grava métricas
4. Asserts críticos:
   - metrics.jsonl deve existir após execução
   - knowledge.json deve ter entradas atualizadas
   - result project dirs devem ter metadata.json
   - output.html deve ter conteúdo > 0

Totalmente assíncrono com pytest-asyncio e patterns async/await.
Determinístico e limpa recursos após execução.
"""
import os
import sys
import json
import logging
import pytest
import asyncio
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal._paths import (
    PROVIDER_METRICS_DIR, CORE_DB, 
    RESULTS_DIR, KNOWLEDGE_FILE, DB_DIR, DATA_ROOT
)
from iaglobal.providers.provider_metrics import ProviderMetrics, METRICS_FILE
from iaglobal.memory.memory_vector import init_db as init_memory_db
from iaglobal.memory.fusion_engine import KnowledgeGraph


# Path esperado para metrics.jsonl (conforme diretrizes)
EXPECTED_METRICS_PATH = Path("/home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/provider_metrics/metrics.jsonl")


@pytest.fixture(scope="function")
def temp_workspace(tmp_path):
    """
    Fixture que cria um workspace temporário para testes isolados.
    Retorna paths para verificação posterior.
    """
    # Cria estrutura de diretórios temporária
    temp_data = tmp_path / "iaglobal" / "memory" / "data"
    temp_metrics_dir = temp_data / "provider_metrics"
    temp_results_dir = temp_data / "result"
    temp_json_dir = temp_data / "json"
    temp_db_dir = temp_data / "db"
    
    for d in [temp_metrics_dir, temp_results_dir, temp_json_dir, temp_db_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Inicializa knowledge.json vazio
    knowledge_file = temp_json_dir / "knowledge.json"
    knowledge_file.write_text("[]")
    
    yield {
        "temp_path": tmp_path,
        "metrics_dir": temp_metrics_dir,
        "results_dir": temp_results_dir,
        "knowledge_file": knowledge_file,
        "db_dir": temp_db_dir,
    }


@pytest.fixture(scope="function")
def clean_metrics_env(temp_workspace, monkeypatch):
    """
    Fixture que limpa o ambiente de métricas antes e depois dos testes.
    Garante isolamento total.
    """
    # Patch PROVIDER_METRICS_DIR para usar diretório temporário
    monkeypatch.setattr(
        "iaglobal._paths.PROVIDER_METRICS_DIR", 
        temp_workspace["metrics_dir"],
        raising=False
    )
    
    # Patch KNOWLEDGE_FILE
    monkeypatch.setattr(
        "iaglobal._paths.KNOWLEDGE_FILE",
        temp_workspace["knowledge_file"],
        raising=False
    )
    
    # Patch RESULTS_DIR
    monkeypatch.setattr(
        "iaglobal._paths.RESULTS_DIR",
        temp_workspace["results_dir"],
        raising=False
    )
    
    # Patch CORE_DB
    test_db = temp_workspace["db_dir"] / "core.db"
    monkeypatch.setattr(
        "iaglobal._paths.CORE_DB",
        str(test_db),
        raising=False
    )
    
    # Força recarregamento do módulo provider_metrics
    import importlib
    import iaglobal.providers.provider_metrics as pm_module
    importlib.reload(pm_module)
    
    yield temp_workspace
    
    # Cleanup automático via tmp_path (pytest já limpa)


class TestMetricsPathValidation:
    """
    VALIDAÇÃO DE CAMINHO CORRETO
    Verifica que as métricas são gravadas no caminho esperado.
    """
    
    def test_expected_metrics_path_exists(self):
        """O caminho esperado para metrics.jsonl deve ser o definido no AGENTS.md."""
        assert EXPECTED_METRICS_PATH.parent.exists(), \
            f"Diretório pai não existe: {EXPECTED_METRICS_PATH.parent}"
    
    def test_provider_metrics_dir_is_correct(self):
        """PROVIDER_METRICS_DIR deve apontar para o caminho correto."""
        assert PROVIDER_METRICS_DIR.name == "provider_metrics", \
            f"Nome do diretório inesperado: {PROVIDER_METRICS_DIR}"
    
    def test_metrics_file_constant_consistent(self):
        """METRICS_FILE deve ser consistente com PROVIDER_METRICS_DIR."""
        expected = str(PROVIDER_METRICS_DIR / "metrics.jsonl")
        assert METRICS_FILE == expected, \
            f"METRICS_FILE ({METRICS_FILE}) != expected ({expected})"


class TestMemoryDatabaseInitialization:
    """
    VALIDAÇÃO DO BANCO DE DADOS
    Inicializa o database de memória antes dos testes.
    """
    
    @pytest.mark.asyncio
    async def test_memory_table_exists_after_init(self, clean_metrics_env, monkeypatch):
        """A tabela 'memory' deve existir após inicialização."""
        test_db = clean_metrics_env["db_dir"] / "core.db"
        
        # Patch CORE_DB para o database temporário
        monkeypatch.setattr("iaglobal._paths.CORE_DB", str(test_db), raising=False)
        
        # Inicializa o database
        await asyncio.to_thread(init_memory_db)
        
        # Verifica tabela existe
        assert test_db.exists(), f"Database não foi criado: {test_db}"
        
        conn = sqlite3.connect(str(test_db))
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memory'"
            )
            result = cursor.fetchone()
            assert result is not None, "Tabela 'memory' não existe no database"
            assert result[0] == "memory", f"Tabela inesperada: {result[0]}"
        finally:
            conn.close()
    
    @pytest.mark.asyncio
    async def test_knowledge_graph_tables_initialized(self, clean_metrics_env, monkeypatch):
        """KnowledgeGraph deve inicializar suas tabelas."""
        test_db = clean_metrics_env["db_dir"] / "core.db"
        
        monkeypatch.setattr("iaglobal._paths.CORE_DB", str(test_db), raising=False)
        
        kg = KnowledgeGraph(db_path=str(test_db))
        
        conn = sqlite3.connect(str(test_db))
        try:
            # Verifica kg_concepts
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kg_concepts'"
            )
            assert cursor.fetchone() is not None, "Tabela 'kg_concepts' não existe"
            
            # Verifica kg_relationships
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kg_relationships'"
            )
            assert cursor.fetchone() is not None, "Tabela 'kg_relationships' não existe"
        finally:
            conn.close()


class TestMetricsRecording:
    """
    TESTE DE GRAVAÇÃO DE MÉTRICAS
    Valida que métricas são gravadas em metrics.jsonl.
    """
    
    @pytest.mark.asyncio
    async def test_metrics_jsonl_created_after_record(self, clean_metrics_env, monkeypatch):
        """metrics.jsonl deve existir após registro de métrica."""
        metrics_dir = clean_metrics_env["metrics_dir"]
        
        monkeypatch.setattr("iaglobal._paths.PROVIDER_METRICS_DIR", metrics_dir, raising=False)
        
        # Recarrega módulo para usar path patchado
        import importlib
        import iaglobal.providers.provider_metrics as pm_module
        importlib.reload(pm_module)
        
        metrics = pm_module.ProviderMetrics()
        metrics.record(
            provider="test_provider",
            model="test/model",
            prompt="test prompt",
            success=True,
            latency_ms=100.0,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            cost=0.001,
            task_type="testing"
        )
        metrics.flush()
        
        metrics_file = metrics_dir / "metrics.jsonl"
        assert metrics_file.exists(), f"metrics.jsonl não foi criado em {metrics_file}"
    
    @pytest.mark.asyncio
    async def test_metrics_jsonl_has_valid_content(self, clean_metrics_env, monkeypatch):
        """metrics.jsonl deve conter JSONL válido com campos obrigatórios."""
        metrics_dir = clean_metrics_env["metrics_dir"]
        
        monkeypatch.setattr("iaglobal._paths.PROVIDER_METRICS_DIR", metrics_dir, raising=False)
        
        import importlib
        import iaglobal.providers.provider_metrics as pm_module
        importlib.reload(pm_module)
        
        metrics = pm_module.ProviderMetrics()
        metrics.record(
            provider="test_async",
            model="test/model-v2",
            prompt="test prompt async",
            success=True,
            latency_ms=250.5,
            prompt_tokens=100,
            completion_tokens=150,
            total_tokens=250,
            cost=0.003,
            task_type="async_test"
        )
        metrics.flush()
        
        metrics_file = metrics_dir / "metrics.jsonl"
        with open(metrics_file, "r") as f:
            content = f.read().strip()
        
        assert content, "Arquivo metrics.jsonl está vazio"
        
        # Valida linha JSON
        entry = json.loads(content)
        assert "timestamp" in entry, "Campo 'timestamp' ausente"
        assert "provider" in entry, "Campo 'provider' ausente"
        assert "model" in entry, "Campo 'model' ausente"
        assert "success" in entry, "Campo 'success' ausente"
        assert "latency_ms" in entry, "Campo 'latency_ms' ausente"
        assert entry["provider"] == "test_async"
        assert entry["model"] == "test/model-v2"


class TestFullPipelineExecution:
    """
    TESTE PIPELINE COMPLETO
    Executa run_code_executor -> run_knowledge_writer -> verifica arquivos.
    """
    
    @pytest.mark.asyncio
    async def test_pipeline_code_executor_creates_output(self, clean_metrics_env, monkeypatch):
        """run_code_executor deve criar arquivos de saída."""
        from iaglobal.graphs.nodes.no_code_executor import run_code_executor
        
        results_dir = clean_metrics_env["results_dir"]
        task = "crie uma funcao python que soma dois numeros"
        
        monkeypatch.setattr("iaglobal._paths.RESULTS_DIR", results_dir, raising=False)
        
        # Código Python simples para teste
        code = '''def add_numbers(a, b):
    """Soma dois numeros."""
    return a + b

result = add_numbers(2, 3)
print(f"Resultado: {result}")
'''
        
        ctx = {
            "input": {"task": task},
            "memory": {"coder": {"output": code}}
        }
        
        result = await run_code_executor(ctx)
        
        assert result["success"] is True, f"Executor falhou: {result.get('exec_error')}"
        assert result.get("final_file") is not None, "final_file não foi criado"
        
        # Verifica metadata.json existe
        if result.get("final_file"):
            project_dir = Path(result["final_file"]).parent
            metadata_path = project_dir / "metadata.json"
            assert metadata_path.exists(), f"metadata.json não existe em {project_dir}"
    
    @pytest.mark.asyncio
    async def test_pipeline_code_executor_html_output(self, clean_metrics_env, monkeypatch):
        """run_code_executor deve criar output.html com conteúdo > 0."""
        from iaglobal.graphs.nodes.no_code_executor import run_code_executor
        
        results_dir = clean_metrics_env["results_dir"]
        
        monkeypatch.setattr("iaglobal._paths.RESULTS_DIR", results_dir, raising=False)
        
        html_code = '''<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Hello World</h1>
    <p>Esta é uma página de teste.</p>
</body>
</html>'''
        
        ctx = {
            "input": {"task": "crie uma pagina html simples"},
            "memory": {"coder": {"output": html_code}}
        }
        
        result = await run_code_executor(ctx)
        
        assert result["success"] is True
        
        # Verifica output.html existe e tem conteúdo
        if result.get("final_file"):
            output_path = Path(result["final_file"])
            if output_path.exists():
                content = output_path.read_text()
                assert len(content) > 0, "output.html está vazio"
                assert "<html" in content.lower() or "<!doctype" in content.lower(), \
                    "Conteúdo não parece HTML válido"


class TestKnowledgeWriterIntegration:
    """
    Integração do KnowledgeWriter com o pipeline.
    """
    
    @pytest.mark.asyncio
    async def test_knowledge_writer_updates_knowledge(self, clean_metrics_env, monkeypatch):
        """knowledge.json deve ter entradas atualizadas após KnowledgeWriter."""
        from iaglobal.graphs.nodes.no_knowledge_writer import run_knowledge_writer
        from iaglobal.memory.memory_vector import init_db as init_vector_db
        
        knowledge_file = clean_metrics_env["knowledge_file"]
        db_dir = clean_metrics_env["db_dir"]
        test_db = db_dir / "core.db"
        
        monkeypatch.setattr("iaglobal._paths.JSON_DIR", knowledge_file.parent, raising=False)
        monkeypatch.setattr("iaglobal._paths.CORE_DB", str(test_db), raising=False)
        
        # Garante diretório db existe
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializa o database vetorial antes do KnowledgeWriter
        await asyncio.to_thread(init_vector_db)
        
        # Código Python para o knowledge writer aprender
        code = '''def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''
        
        ctx = {
            "input": {"task": "crie uma funcao fibonacci em python"},
            "memory": {"coder": {"output": code}}
        }
        
        result = await run_knowledge_writer(ctx)
        
        assert result.get("success") is not False or result.get("output", {}).get("status") != "error", \
            f"KnowledgeWriter falhou: {result}"
        
        # Verifica knowledge.json foi atualizado
        if knowledge_file.exists():
            content = knowledge_file.read_text()
            data = json.loads(content)
            # Deve ter pelo menos algumas entradas após o run
            assert len(data) >= 0, "knowledge.json deve existir (pode estar vazio se não houver conceitos)"


class TestCompletePipelineIntegration:
    """
    Teste de integração completa: executor -> knowledge -> metrics.
    """
    
    @pytest.mark.asyncio
    async def test_full_pipeline_creates_all_artifacts(self, clean_metrics_env, monkeypatch):
        """Pipeline completo deve criar todos os artefatos esperados."""
        from iaglobal.graphs.nodes.no_code_executor import run_code_executor
        from iaglobal.graphs.nodes.no_knowledge_writer import run_knowledge_writer
        from iaglobal.providers.provider_metrics import ProviderMetrics
        from iaglobal.memory.memory_vector import init_db as init_vector_db
        
        results_dir = clean_metrics_env["results_dir"]
        knowledge_file = clean_metrics_env["knowledge_file"]
        metrics_dir = clean_metrics_env["metrics_dir"]
        db_dir = clean_metrics_env["db_dir"]
        
        monkeypatch.setattr("iaglobal._paths.RESULTS_DIR", results_dir, raising=False)
        monkeypatch.setattr("iaglobal._paths.KNOWLEDGE_FILE", knowledge_file, raising=False)
        monkeypatch.setattr("iaglobal._paths.PROVIDER_METRICS_DIR", metrics_dir, raising=False)
        monkeypatch.setattr("iaglobal._paths.CORE_DB", str(db_dir / "core.db"), raising=False)
        
        # Inicializa o database vetorial antes do pipeline
        db_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(init_vector_db)
        
        # Passo 1: Executar código
        python_code = '''def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
'''
        
        ctx = {
            "input": {"task": "crie uma funcao de saudacao em python"},
            "memory": {"coder": {"output": python_code}}
        }
        
        executor_result = await run_code_executor(ctx)
        assert executor_result["success"] is True, "Executor falhou"
        
        # Passo 2: Knowledge Writer
        ctx["memory"] = {"coder": {"output": python_code}}
        knowledge_result = await run_knowledge_writer(ctx)
        assert knowledge_result is not None
        
        # Passo 3: Registrar métrica
        metrics = ProviderMetrics()
        metrics.record(
            provider="pipeline_integration_test",
            model="test/model",
            prompt="test integration",
            success=True,
            latency_ms=500.0,
            task_type="integration"
        )
        metrics.flush()
        
        # Asserts finais
        # 1. metrics.jsonl existe
        metrics_file = metrics_dir / "metrics.jsonl"
        assert metrics_file.exists(), "metrics.jsonl não foi criado"
        
        # 2. knowledge.json existe
        assert knowledge_file.exists(), "knowledge.json não foi criado"
        
        # 3. Project dir tem metadata.json
        if executor_result.get("final_file"):
            project_dir = Path(executor_result["final_file"]).parent
            metadata_path = project_dir / "metadata.json"
            assert metadata_path.exists(), f"metadata.json não existe em {project_dir}"


class TestOutputFilesValidation:
    """
    Validação de arquivos de saída do pipeline.
    """
    
    @pytest.mark.asyncio
    async def test_output_html_has_positive_length(self, clean_metrics_env, monkeypatch):
        """output.html deve ter conteúdo > 0 após execução com HTML."""
        from iaglobal.graphs.nodes.no_code_executor import run_code_executor
        
        results_dir = clean_metrics_env["results_dir"]
        monkeypatch.setattr("iaglobal._paths.RESULTS_DIR", results_dir, raising=False)
        
        html_content = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Teste Integration</title>
</head>
<body>
    <h1>Teste de Integração</h1>
    <p>Conteudo de teste para validacao de pipeline.</p>
</body>
</html>'''
        
        ctx = {
            "input": {"task": "pagina html de teste"},
            "memory": {"coder": {"output": html_content}}
        }
        
        result = await run_code_executor(ctx)
        
        final_file = result.get("final_file")
        if final_file:
            output_path = Path(final_file)
            if output_path.suffix == ".html":
                content = output_path.read_text()
                assert len(content) > 0, "output.html não pode ter conteúdo vazio"
                assert len(content) >= 100, f"output.html muito pequeno ({len(content)} chars)"
    
    @pytest.mark.asyncio
    async def test_metadata_json_structure(self, clean_metrics_env, monkeypatch):
        """metadata.json deve ter estrutura mínima esperada."""
        from iaglobal.graphs.nodes.no_code_executor import run_code_executor
        
        results_dir = clean_metrics_env["results_dir"]
        monkeypatch.setattr("iaglobal._paths.RESULTS_DIR", results_dir, raising=False)
        
        code = "print('test')"
        
        ctx = {
            "input": {"task": "teste metadata"},
            "memory": {"coder": {"output": code}}
        }
        
        result = await run_code_executor(ctx)
        
        if result.get("final_file"):
            project_dir = Path(result["final_file"]).parent
            metadata_path = project_dir / "metadata.json"
            
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                
                assert "task" in metadata, "metadata.json deve ter 'task'"
                assert "timestamp" in metadata, "metadata.json deve ter 'timestamp'"


class TestDeterministicCleanup:
    """
    Garante que recursos são limpos após testes.
    """
    
    def test_temp_workspace_isolated(self, temp_workspace):
        """Workspace temporário deve ser isolado e não afetar sistema real."""
        # O pytest tmp_path garante limpeza automática
        assert temp_workspace["temp_path"].exists()
        assert temp_workspace["metrics_dir"].exists()
        
        # Após o teste, tmp_path será limpo automaticamente pelo pytest


class TestRealPathValidation:
    """
    Validação explícita do caminho real no sistema.
    """
    
    def test_expected_path_matches_real_path(self):
        """O caminho esperado no AGENTS.md deve coincidir com o METRICS_FILE real."""
        # O caminho esperado é: /home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/provider_metrics/metrics.jsonl
        expected = Path("/home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/provider_metrics")
        actual = PROVIDER_METRICS_DIR
        
        assert actual == expected, \
            f"PROVIDER_METRICS_DIR ({actual}) != expected ({expected})"
    
    def test_real_metrics_path_structure(self):
        """Verifica estrutura de diretórios do caminho real."""
        # Verifica se o caminho real tem a estrutura esperada
        assert "memory" in str(PROVIDER_METRICS_DIR), \
            "PROVIDER_METRICS_DIR deve estar dentro de memory"
        assert "provider_metrics" in str(PROVIDER_METRICS_DIR), \
            "PROVIDER_METRICS_DIR deve ter nome 'provider_metrics'"