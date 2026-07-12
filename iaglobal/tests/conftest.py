from pathlib import Path
import pytest

TESTS_TEMP = Path(__file__).parent / "temp"


@pytest.fixture(scope="session")
def tests_temp_dir() -> Path:
    TESTS_TEMP.mkdir(parents=True, exist_ok=True)
    return TESTS_TEMP


@pytest.fixture(autouse=True)
def _clean_tests_temp(tests_temp_dir: Path):
    yield
    for child in tests_temp_dir.iterdir():
        if child.name == "__pycache__":
            continue
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            import shutil
            shutil.rmtree(child)
