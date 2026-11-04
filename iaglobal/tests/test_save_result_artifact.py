# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do contrato de ``save_result_artifact`` em ``iaglobal/_paths.py``.

Cobre a Opção B aplicada ao bug pré-existente descoberto pelo E2E:
``pipeline/engine.py:_save_script`` chama
``save_result_artifact(state.prompt, {}, code, preferred_ext)`` com 4
argumentos, mas a função só aceitava 3. O fix estende a assinatura com
``preferred_ext: str = ""`` — preservando o comportamento histórico
(baseado em ``_detect_extension(code, task)``) quando vazio.
"""

from pathlib import Path

import pytest


@pytest.fixture
def paths_module():
    """Importa ``iaglobal._paths`` e valida que ``save_result_artifact`` vive nele.

    Garante rastreabilidade do contrato testado: cada asserção referencia o
    módulo canônico ``iaglobal._paths`` (não cópia, não mock parcial).
    """
    import iaglobal._paths as pm

    assert hasattr(pm, "save_result_artifact"), (
        "iaglobal._paths deve exportar save_result_artifact — "
        "verifique se o fix Opção B foi aplicado"
    )
    assert pm.save_result_artifact.__module__ == "iaglobal._paths", (
        f"save_result_artifact pertence a {pm.save_result_artifact.__module__}, "
        "esperado iaglobal._paths"
    )
    return pm


@pytest.fixture
def isolated_results_dir(tests_temp_dir: Path, monkeypatch, paths_module):
    """Aponta ``RESULTS_DIR`` e arquivos de counter/lock para ``tests_temp_dir``.

    Usa o módulo ``paths_module`` (fixture acima) como referência canônica
    — evita que o monkeypatch atinja outro módulo carregado por engano.
    """
    monkeypatch.setattr(paths_module, "RESULTS_DIR", tests_temp_dir)
    monkeypatch.setattr(
        paths_module, "_RESULT_COUNTER_FILE", tests_temp_dir / ".counter.json"
    )
    monkeypatch.setattr(
        paths_module, "_RESULT_LOCK_FILE", tests_temp_dir / ".counter.lock"
    )
    return tests_temp_dir


# ── 1. Comportamento legado (preferred_ext ausente) ──


def test_save_result_artifact_sem_preferred_ext_preserva_comportamento(
    isolated_results_dir: Path, paths_module
):
    """Sem preferred_ext, a extensão vem de _detect_extension (código Python → .py).

    Referência canônica: ``iaglobal._paths.save_result_artifact``.
    """
    project_dir = paths_module.save_result_artifact(
        task="teste legacy",
        files={},
        code="def hello():\n    print('hi')\n",
    )

    assert (project_dir / "output.py").exists()
    assert not (project_dir / "output").exists()
    assert (project_dir / "metadata.json").exists()
    # Garantia anti-regressão: não poluiu o RESULTS_DIR real.
    assert "memory/data/result" not in str(project_dir)


def test_save_result_artifact_com_preferred_ext_vazio_fallback_legado(
    isolated_results_dir: Path, paths_module
):
    """preferred_ext='' é equivalente a omitir — usa detecção automática."""
    project_dir = paths_module.save_result_artifact(
        task="teste vazio",
        files={},
        code="def hello(): pass\n",
        preferred_ext="",
    )
    assert (project_dir / "output.py").exists()


# ── 2. preferred_ext informado sobrescreve a detecção ──


def test_save_result_artifact_com_preferred_ext_explicito(
    isolated_results_dir: Path, paths_module
):
    """preferred_ext='.txt' força extensão .txt mesmo se o código parece Python."""
    project_dir = paths_module.save_result_artifact(
        task="teste txt",
        files={},
        code="def hello(): pass\n",  # _detect_extension escolheria .py
        preferred_ext=".txt",
    )
    assert (project_dir / "output.txt").exists()
    assert not (project_dir / "output.py").exists()


def test_save_result_artifact_preferred_ext_sem_ponto(
    isolated_results_dir: Path, paths_module
):
    """preferred_ext aceita 'py' sem ponto — apenas concatena em output<ext>."""
    project_dir = paths_module.save_result_artifact(
        task="teste py",
        files={},
        code="x = 1",
        preferred_ext="py",
    )
    assert (project_dir / "outputpy").exists()


# ── 3. Compatibilidade com callers históricos (kwargs) ──


def test_save_result_artifact_kwargs_consumidores_antigos(
    isolated_results_dir: Path, paths_module
):
    """Chamadas via kwargs (no_code_executor, no_result_agent) continuam funcionando."""
    project_dir = paths_module.save_result_artifact(
        task="x", files={}, code="def f(): pass\n"
    )
    assert (project_dir / "output.py").exists()


# ── 4. files populado (não usa code) ──


def test_save_result_artifact_com_files_nao_cria_output(
    isolated_results_dir: Path, paths_module
):
    """Quando files não está vazio, o code é ignorado — comportamento histórico."""
    project_dir = paths_module.save_result_artifact(
        task="multi-file",
        files={"src/main.py": "x = 1\n", "README.md": "# hi\n"},
        code="def hello(): pass\n",
        preferred_ext=".txt",
    )
    assert (project_dir / "src" / "main.py").exists()
    assert (project_dir / "README.md").exists()
    # Mesmo com preferred_ext, files populado suprime output.* (regra histórica)
    assert not list(project_dir.glob("output.*"))


# ── 5. Caller real (pipeline/engine.py:_save_script) ──


def test_engine_save_script_com_preferred_ext_compativel(
    isolated_results_dir: Path, paths_module
):
    """A incompatibilidade descoberta pelo E2E: caller passa 4 args, função aceita.

    Referência canônica: AGENTS.md → "💾 Persistence Authority — _paths.py is
    Mandatory". Toda persistência em disco passa por ``iaglobal/_paths.py``;
    este teste é a regressão que prova que o contrato caller↔função está
    alinhado após o incidente ``pipeline/engine.py:840``.
    """
    from unittest.mock import MagicMock

    from iaglobal.pipeline.engine import PipelineEngine
    from iaglobal.pipeline.pipelinestate import PipelineState

    state = PipelineState(task_id="t1", prompt="hello")
    state._generated_code = "def hello(): pass\n"
    state.intent = "code"

    engine = PipelineEngine(orchestrator=MagicMock())
    # Sem o fix (preferred_ext ausente em save_result_artifact), este
    # _save_script levanta TypeError por causa do 4º arg.
    result = engine._save_script(state)
    assert result is not None
    assert result.name.startswith("output")
    # Resultado gravado em tests_temp_dir (via fixture isolated_results_dir),
    # nunca em memory/data/result/ (regra AGENTS.md)
    assert "memory/data/result" not in str(result)


# ── 6. metadata sempre presente ──


def test_save_result_artifact_metadata_sempre(isolated_results_dir: Path, paths_module):
    """metadata.json é gravado independentemente de files ou code."""
    project_dir = paths_module.save_result_artifact(
        task="meta-check", files={}, code="", preferred_ext=".py"
    )
    assert (project_dir / "metadata.json").exists()
    import json

    meta = json.loads((project_dir / "metadata.json").read_text())
    assert meta["task"] == "meta-check"
    assert "timestamp" in meta
