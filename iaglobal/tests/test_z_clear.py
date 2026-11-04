# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste Z — Limpeza pós-suíte.

Como pytest executa arquivos em ordem alfabética (``pytest --collect-only``
confirma ordem), este arquivo roda por último (Z = fim do alfabeto). Se
qualquer teste anterior falhou, o pytest aborta a sessão com exit≠0
antes de chegar aqui — então a presença deste teste na saída **garante**
que todos os testes anteriores passaram.

Política:
  - Rodou este teste? → Tudo passou → limpa artefatos.
  - pytest parou antes? → Alguma coisa falhou → preserva evidência.

Cobre:
  - Reset de ``TESTS_DATA_DIR`` (subpastas e arquivos de teste).
  - Reset de artefatos que vazaram para ``memory/data/json/`` (best_genome,
    ga_telemetry) — sintoma de regressão na diretriz AGENTS.md
    "Persistence Authority — _paths.py is Mandatory".
  - Preserva arquivos com marcador ``.keep`` (versionamento intencional).

Invocação:
  - Default: roda como último teste do ``pytest iaglobal/tests/``.
  - Para checar sem limpar: ``pytest --collect-only`` lista este teste
    por último.
"""

from pathlib import Path


from iaglobal._paths import DATA_ROOT, TESTS_DATA_DIR


def _cleanup_tests_artifacts(tests_root: Path) -> tuple[int, list[str]]:
    """Remove arquivos/subpastas transitórios do ``TESTS_DATA_DIR``.

    Preserva qualquer arquivo que comece com ``.`` ou que tenha um
    marcador ``.keep`` em si ou em algum ancestral (versionamento).
    """
    if not tests_root.exists():
        return 0, []

    removed_count = 0
    removed_paths: list[str] = []

    for path in sorted(tests_root.rglob("*"), reverse=True):
        if path.name.startswith("."):
            continue
        if any(parent.name == ".keep" for parent in path.parents):
            continue
        if path.is_dir():
            if not any(path.iterdir()):
                removed_paths.append(str(path))
                path.rmdir()
                removed_count += 1
        else:
            removed_paths.append(str(path))
            path.unlink()
            removed_count += 1

    return removed_count, removed_paths


def _cleanup_leaked_lib_files() -> tuple[int, list[str]]:
    """Remove artefatos que vazaram para ``memory/data/json/`` durante testes.

    Esses arquivos são sintoma de testes que não isolaram corretamente
    (violação da regra AGENTS.md "_paths.py is Mandatory"). Se persistem
    após exit 0, indica regressão arquitetural.
    """
    json_dir = DATA_ROOT / "json"
    targets = [
        json_dir / "best_genome.json",
        json_dir / "ga_telemetry.json",
    ]
    removed_paths: list[str] = []
    for path in targets:
        if path.exists():
            removed_paths.append(str(path))
            path.unlink()
    return len(removed_paths), removed_paths


def test_z_clean_artifacts_after_full_pass():
    """Roda por último; limpa artefatos se (e somente se) chegou até aqui.

    Pré-condição implícita: pytest só chega a este teste se todos os
    anteriores passaram. Em caso de falha anterior, pytest aborta com
    exit≠0 e este teste não é invocado — preservando evidência de debug.
    """
    n_tests, tests_paths = _cleanup_tests_artifacts(TESTS_DATA_DIR)
    n_lib, lib_paths = _cleanup_leaked_lib_files()

    summary = (
        f"limpos {n_tests} arquivo(s) em TESTS_DATA_DIR "
        f"e {n_lib} vazamento(s) em memory/data/json/"
    )
    if tests_paths or lib_paths:
        detail = "\n  ".join(tests_paths + lib_paths)
        print(f"\n[Z-clean] {summary}:\n  {detail}")
    else:
        print(f"\n[Z-clean] {summary} (nada a fazer)")

    assert True
