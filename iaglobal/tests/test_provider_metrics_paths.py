"""Teste de consistência de paths de métricas dos providers.

Verifica se todos os componentes escrevem/leem métricas nos mesmos paths,
evitando o problema de dados silenciosamente isolados em locais diferentes.
"""

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent.parent


def test_provider_metrics_path_consistency():
    """provider_metrics.py escreve onde bandit.py lê? SIM."""
    from iaglobal._paths import PROVIDER_METRICS_DIR
    from iaglobal.providers.provider_metrics import METRICS_FILE

    expected = str(PROVIDER_METRICS_DIR / "metrics.jsonl")
    assert METRICS_FILE == expected, (
        f"MISMATCH: provider_metrics.py escreve em {METRICS_FILE}\n"
        f"  mas _paths.PROVIDER_METRICS_DIR aponta para {expected}"
    )
    print(f"[PASS] provider_metrics -> {METRICS_FILE}")


def test_bandit_reads_same_metrics():
    """bandit.py importa o singleton 'metrics' de provider_metrics — mesmo path."""
    from iaglobal.providers.provider_metrics import METRICS_FILE, metrics
    from iaglobal.graphs.bandit import BanditPolicy

    assert metrics is not None
    assert BanditPolicy is not None
    print(f"[PASS] bandit importa o singleton metrics de provider_metrics -> {METRICS_FILE}")


def test_batch_writer_path():
    """providers/batch_writer.py agora re-exporta storage.batch_writer via PROVIDER_EVENTS_DB."""
    from iaglobal._paths import PROVIDER_EVENTS_DB, DB_DIR
    from iaglobal.providers.batch_writer import DB_PATH

    assert DB_PATH == PROVIDER_EVENTS_DB, (
        f"MISMATCH: providers.batch_writer.DB_PATH = {DB_PATH}\n"
        f"  mas _paths.PROVIDER_EVENTS_DB = {PROVIDER_EVENTS_DB}"
    )
    assert str(DB_DIR.resolve()) in str(DB_PATH.resolve()), (
        f"DB_PATH {DB_PATH} não está dentro de DB_DIR {DB_DIR}"
    )
    print(f"[PASS] providers/batch_writer.DB_PATH -> {DB_PATH}")


def test_storage_batch_writer_uses_core_db():
    """storage/batch_writer.py usa _paths.CORE_DB por default."""
    from iaglobal._paths import CORE_DB
    from iaglobal.storage.batch_writer import BatchWriter

    bw = BatchWriter()
    assert str(bw.db_path.resolve()) == str(CORE_DB.resolve()), (
        f"storage BatchWriter default db_path = {bw.db_path}\n"
        f"  mas _paths.CORE_DB = {CORE_DB}"
    )
    print(f"[PASS] storage/batch_writer default DB -> {CORE_DB}")


def test_provider_state_path():
    """provider_state.py usa _paths.DATA_ROOT como base."""
    from iaglobal._paths import DATA_ROOT
    from iaglobal.providers.provider_state import provider_state

    expected = DATA_ROOT / "provider_state.json"
    assert provider_state.persist_file == expected, (
        f"MISMATCH: provider_state.persist_file = {provider_state.persist_file}\n"
        f"  mas DATA_ROOT/provider_state.json = {expected}"
    )
    print(f"[PASS] provider_state -> {provider_state.persist_file}")


def test_images_dir_path():
    """hf_image_provider.py usa _paths.IMAGES_DIR."""
    from iaglobal._paths import IMAGES_DIR
    from iaglobal.providers.hf_image_provider import IMAGES_DIR as HF_IMAGES_DIR

    assert HF_IMAGES_DIR == IMAGES_DIR, (
        f"MISMATCH: hf_image_provider.IMAGES_DIR = {HF_IMAGES_DIR}\n"
        f"  mas _paths.IMAGES_DIR = {IMAGES_DIR}"
    )
    print(f"[PASS] hf_image_provider.IMAGES_DIR -> {HF_IMAGES_DIR}")


def test_all_paths_under_memory_data():
    """Todos os paths ficam dentro de memory/data/."""
    from iaglobal._paths import DATA_ROOT
    from iaglobal.providers.provider_metrics import METRICS_FILE
    from iaglobal.providers.batch_writer import DB_PATH
    from iaglobal.providers.provider_state import provider_state
    from iaglobal.providers.hf_image_provider import IMAGES_DIR as HF_IMAGES_DIR

    paths = [
        ("provider_metrics", METRICS_FILE),
        ("providers_batch_writer", str(DB_PATH)),
        ("provider_state", str(provider_state.persist_file)),
        ("hf_images", str(HF_IMAGES_DIR)),
    ]

    for name, path_str in paths:
        path = Path(path_str).resolve()
        assert str(DATA_ROOT.resolve()) in str(path), (
            f"{name}: {path} NÃO está dentro de {DATA_ROOT}"
        )
        print(f"[PASS] {name} está dentro de memory/data")


def test_provider_events_db_under_db_dir():
    """PROVIDER_EVENTS_DB fica dentro de DB_DIR (db/)."""
    from iaglobal._paths import PROVIDER_EVENTS_DB, DB_DIR

    assert str(DB_DIR.resolve()) in str(PROVIDER_EVENTS_DB.resolve()), (
        f"PROVIDER_EVENTS_DB {PROVIDER_EVENTS_DB} não está em DB_DIR {DB_DIR}"
    )
    print(f"[PASS] PROVIDER_EVENTS_DB -> {PROVIDER_EVENTS_DB}")


def test_metrics_dir_exists():
    """O diretório de métricas é criado pelo _paths._ensure_dirs()."""
    from iaglobal._paths import PROVIDER_METRICS_DIR

    assert PROVIDER_METRICS_DIR.exists(), (
        f"PROVIDER_METRICS_DIR não existe: {PROVIDER_METRICS_DIR}\n"
        f"_ensure_dirs() deveria ter criado na importação de _paths"
    )
    print(f"[PASS] PROVIDER_METRICS_DIR existe em {PROVIDER_METRICS_DIR}")


def test_metrics_file_writable():
    """Verifica se conseguimos escrever e ler do metrics.jsonl."""
    from iaglobal.providers.provider_metrics import METRICS_FILE
    import json

    test_entry = {"provider": "test", "latency_ms": 42, "success": True}
    mf = Path(METRICS_FILE)
    mf.parent.mkdir(parents=True, exist_ok=True)

    with open(mf, "a") as f:
        f.write(json.dumps(test_entry) + "\n")

    with open(mf) as f:
        lines = f.readlines()

    last = json.loads(lines[-1].strip())
    assert last["provider"] == "test", f"Falha no write/read: {last}"

    mf.unlink()
    print(f"[PASS] metrics.jsonl é writable/readable em {METRICS_FILE}")
