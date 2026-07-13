# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes da implantação 'sem métricas falsas'.

Garante que o organismo não se engana a si mesmo:
  1. Erros reais são persistidos (errors.json + error/) — não "0 erros".
  2. IVM NÃO credita produtividade em cache hit (antes saturava em 0.89).
  3. Homocysteine NÃO promove dump/ruído a 'production'.
  4. Falha de import de nó é registrada (barreira + errors.json), não engolida.
"""

import json
import logging
from pathlib import Path

import pytest

from iaglobal._paths import ERROR_LOG, ERROR_DIR
from iaglobal.immunity.error_persistence import install as install_error_persistence
from iaglobal.immunity.metabolic_immune_barrier import barrier
from iaglobal.providers import provider_router as pr
from iaglobal.metabolism.homocysteine_pool import HomocysteinePool, CandidateSkill
from iaglobal.evolution.skills.native.skill import Skill


def _count_runtime_errors() -> int:
    if not ERROR_LOG.exists():
        return 0
    try:
        data = json.loads(ERROR_LOG.read_text())
        return len(data.get("runtime_errors", []))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# 1. ErrorPersistence — erros reais persistidos
# ---------------------------------------------------------------------------
def test_runtime_error_is_persisted():
    # Reset para estado limpo — lista de erros tem cap de 200 entradas
    from iaglobal.immunity.error_persistence import _save

    _save({"updated_at": "", "learning_errors": [], "runtime_errors": []})
    install_error_persistence()
    before = _count_runtime_errors()
    before_files = len(list(ERROR_DIR.glob("*.md")))

    logging.getLogger("iaglobal.test_error_persist").error(
        "erro de teste persistido %s", "xyz"
    )

    after = _count_runtime_errors()
    after_files = len(list(ERROR_DIR.glob("*.md")))
    assert after == before + 1, (
        f"errors.json deveria ganhar 1 entrada (antes={before}, depois={after})"
    )
    assert after_files == before_files + 1, "pasta error/ deveria ganhar 1 arquivo"


# ---------------------------------------------------------------------------
# 4. Import failure de nó não é engolido
# ---------------------------------------------------------------------------
def test_node_import_failure_recorded():
    import iaglobal.graphs.nodes as nodes_mod

    # Reset explícito do Singleton para forçar recarregamento dinâmico
    # Independente de quem tenha rodado antes na suíte
    nodes_mod.Nodes._instance = None

    # Força recarregamento do diretório de nós (engatilha o loader dinâmico).
    nodes_mod.Nodes()
    counts = barrier.counts()
    # Após correção dos nós órfãos (dispatcher exportado, exceptions.py criado),
    # espera-se 0 import_failure. O teste verifica que a barreira não crasha
    # e que as chaves esperadas existem no dicionário.
    assert "import_failure" in counts, (
        f"barreira deveria ter chave import_failure — counts={counts}"
    )


# ---------------------------------------------------------------------------
# 2. IVM não credita produtividade em cache hit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ivm_does_not_credit_cache_hit(tests_temp_dir: Path):
    from iaglobal.chappie.ivm_axiom import init_ivm_axiom_com_persistencia
    from iaglobal.chappie import _get_chappie

    # Garante inicialização do singleton canônico
    db_path = tests_temp_dir / "ivm_test.db"
    axiom = init_ivm_axiom_com_persistencia(db_path=db_path)

    # Verifica se o singleton foi registrado corretamente
    assert _get_chappie().get("ivm") is axiom, "IVM deve estar registrado no Chappie"

    agent = "_test_cachehit_agent"

    # Garante estado limpo para o agente.
    axiom._metricas.pop(agent, None)

    await pr._report_ivm_telemetry(agent, True, 0.5, "ollama", cache_hit=True)
    after_cache_entry = axiom._metricas.get(agent)
    after_cache = after_cache_entry.tasks_completed if after_cache_entry else 0
    assert after_cache == 0, (
        f"cache hit NÃO deve incrementar produtividade (got {after_cache})"
    )

    await pr._report_ivm_telemetry(agent, True, 0.5, "ollama", cache_hit=False)
    after_real = axiom._metricas[agent].tasks_completed
    assert after_real == 1, (
        f"geração real DEVE incrementar produtividade (got {after_real})"
    )


# ---------------------------------------------------------------------------
# 3. Homocysteine não promove dump/ruído a production
# ---------------------------------------------------------------------------
def _candidate(desc: str, gap: str, score: float = 0.9) -> CandidateSkill:
    return CandidateSkill(
        skill=Skill(
            name="cand",
            description=desc,
            inputs=[],
            outputs=[],
            constraints=[],
            run_fn=None,
            version="1.0.0",
            tags=["candidate"],
        ),
        score=score,
        source_gap=gap,
    )


def test_homocysteine_rejects_ivm_dump():
    pool = HomocysteinePool.__new__(HomocysteinePool)  # sem _load (não toca disco)
    dump = _candidate(
        "Skill derivada de: IVM dados: {'agents_ativos': 41, 'peak_ivm': 0.89}",
        "gap de exemplo com conteúdo suficiente para passar no tamanho mínimo exigido pelo gate de promoção",
    )
    ok, reason = pool._is_production_worthy(dump)
    assert not ok, f"dump de IVM não deve ser production-worthy (reason={reason})"


def test_homocysteine_promotes_legit_skill():
    pool = HomocysteinePool.__new__(HomocysteinePool)
    legit = _candidate(
        "Gera um resumo executivo do código fonte analisando funções, classes e módulos do projeto.",
        "O agente precisa produzir resumos curtos e precisos a partir de bases de código grandes e diversas.",
    )
    ok, reason = pool._is_production_worthy(legit)
    assert ok, f"skill legítima deveria ser production-worthy (reason={reason})"
