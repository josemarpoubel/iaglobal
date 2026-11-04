from pathlib import Path
import pytest

from iaglobal._paths import TESTS_DATA_DIR


@pytest.fixture(scope="session")
def tests_temp_dir() -> Path:
    """Diretório canônico para artefatos da suíte de testes.

    Aponta para ``iaglobal/memory/data/temp/tests/`` (exposto via
    :data:`iaglobal._paths.TESTS_DATA_DIR`). Persistente e versionável —
    testes que precisam de estado cross-session acumulam aqui; testes
    que precisam de isolamento por-run devem usar subpastas dedicadas.
    """
    TESTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TESTS_DATA_DIR
