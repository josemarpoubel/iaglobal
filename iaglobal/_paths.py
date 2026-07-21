# iaglobal/_paths.py

import json
import os
import fcntl

from pathlib import Path

# =========================================================
# ROOT DO SISTEMA (SOURCE OF TRUTH)
# =========================================================

# Raiz do pacote iaglobal (onde _paths.py está)
PACKAGE_DIR = Path(__file__).resolve().parent

# Raiz do projeto (onde pyproject.toml, docs/, cli.py estão)
PROJECT_ROOT = PACKAGE_DIR.parent

# =========================================================
# DATA LAYER (ORGANISM-SCOPED — override via env var)
# =========================================================

_organism_data_root = os.environ.get("ORGANISM_DATA_ROOT")
DATA_ROOT = (
    Path(_organism_data_root)
    if _organism_data_root
    else (PACKAGE_DIR / "memory" / "data")
)

# =========================================================
# STORAGE TYPE SELECTORS
# =========================================================

# MEMORY_STORAGE_TYPE: sqlite (default) | json | cbor2
# Controla o backend de persistência das memórias STM/LTM.
MEMORY_STORAGE_TYPE = os.environ.get("MEMORY_STORAGE_TYPE", "sqlite")

# METABOLIC_STORAGE_TYPE: auto (default) | cbor2 | json | sqlite
# Controla quais fontes o MetabolicDataAdapter consulta.
# auto = todas as fontes disponíveis (epigenetic + pools + sqlite)
METABOLIC_STORAGE_TYPE = os.environ.get("METABOLIC_STORAGE_TYPE", "auto")

# Subdiretórios organizados
JSON_DIR = DATA_ROOT / "json"
DB_DIR = DATA_ROOT / "db"
CBOR2_DIR = DATA_ROOT / "cbor2"
SYNTHESIS_JSON_DIR = JSON_DIR / "synthesis"
SYNTHESIS_CBOR2 = CBOR2_DIR / "synthesis_index.cbor2"
MEMORY_DIR = DATA_ROOT
BACKUP_DIR = DATA_ROOT / "memory_backups"
CACHE_DIR = DATA_ROOT / "cache"
MEMORY_SWAP_DIR = CACHE_DIR / "memory_swap"
SEARCH_SWAP_DIR = CACHE_DIR / "search_swap"
LOG_DIR = DATA_ROOT / "logs"
SCRIPTS_DIR = DATA_ROOT / "script"
TEMP_DIR = DATA_ROOT / "temp"

# =========================================================
# RESULT OUTPUT (projetos numerados sequencialmente)
# =========================================================

RESULTS_DIR = DATA_ROOT / "result"
_RESULT_COUNTER_FILE = RESULTS_DIR / ".counter.json"
_RESULT_LOCK_FILE = RESULTS_DIR / ".counter.lock"

# =========================================================
# COMPATIBILITY LAYER
# =========================================================

DATA_DIR = MEMORY_DIR
BACKUP_DIR_LEGACY = BACKUP_DIR

# =========================================================
# DATABASES (SINGLE SOURCE OF TRUTH)
# =========================================================

CORE_DB = DB_DIR / "core.db"
CACHE_DB = DB_DIR / "cache.db"
MEMORIES_DB = DB_DIR / "memories.db"
SNAPSHOTS_DIR = DATA_ROOT / "snapshots"
WORK_DIR = MEMORY_DIR / "work"
PROVIDER_METRICS_DIR = DATA_ROOT / "provider_metrics"
PROVIDER_EVENTS_DB = DB_DIR / "provider_events.db"
IMAGES_DIR = DATA_ROOT / "generated_images"
MONITORED_DIR = DATA_ROOT / "storage"
KNOWLEDGE_FILE = JSON_DIR / "knowledge.json"
DOCS_TEMP_DIR = TEMP_DIR / "documentation"
SANDBOX_DIR = TEMP_DIR / "sandbox_exec"
META_EVOLUTION_FILE = JSON_DIR / "meta_evolution.json"
EVOLUTION_BACKLOG_FILE = JSON_DIR / "evolution_backlog.json"
SAME_POOL_FILE = JSON_DIR / "same_pool.json"
HOMOCYSTEINE_POOL_FILE = JSON_DIR / "homocysteine_pool.json"
GLUTATHIONE_POOL_FILE = JSON_DIR / "glutathione_pool.json"
CHOLINE_POOL_FILE = TEMP_DIR / "choline_pool.json"
MTA_POOL_FILE = TEMP_DIR / "mta_pool.json"
METHYLATION_ENGINE_FILE = JSON_DIR / "methylation_engine.json"
ERROR_LOG = JSON_DIR / "errors.json"
ERROR_DIR = DATA_ROOT / "error"

# =========================================================
# ARTIFACTS / EMBEDDINGS
# =========================================================

EMBEDDINGS_DB = CBOR2_DIR / "embeddings.cbor2"

# =========================================================
# DOCUMENTATION / OBSERVABILITY
# =========================================================

DOCS_DIR = PROJECT_ROOT / "docs"
EVOLUTION_DOC = DOCS_DIR / "evolucao_cerebral.md"

# =========================================================
# GUARANTEE LAYER (AUTO-BOOTSTRAP DO SISTEMA)
# =========================================================


def _ensure_dirs():
    """Garante estrutura mínima do sistema antes de qualquer execução."""
    critical_dirs = [
        DATA_ROOT,
        MEMORY_DIR,
        JSON_DIR,
        DB_DIR,
        CBOR2_DIR,
        BACKUP_DIR,
        CACHE_DIR,
        MEMORY_SWAP_DIR,
        SEARCH_SWAP_DIR,
        LOG_DIR,
        DOCS_DIR,
        SCRIPTS_DIR,
        TEMP_DIR,
        RESULTS_DIR,
        SNAPSHOTS_DIR,
        WORK_DIR,
        PROVIDER_METRICS_DIR,
        IMAGES_DIR,
        MONITORED_DIR,
        DOCS_TEMP_DIR,
        SANDBOX_DIR,
        ERROR_DIR,
        SYNTHESIS_JSON_DIR,
    ]
    for d in critical_dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Garante arquivos JSON iniciais para evitar logs de "não persistido"
    list_files = (
        KNOWLEDGE_FILE,
        HOMOCYSTEINE_POOL_FILE,
        GLUTATHIONE_POOL_FILE,
        SAME_POOL_FILE,
        META_EVOLUTION_FILE,
        EVOLUTION_BACKLOG_FILE,
    )
    for f in list_files:
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("[]")
    # errors.json requer estrutura de dict (runtime_errors + learning_errors)
    if not ERROR_LOG.exists():
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        ERROR_LOG.write_text(
            '{"updated_at": "", "learning_errors": [], "runtime_errors": []}'
        )


try:
    _ensure_dirs()
except Exception as e:
    from iaglobal.utils.logger import logger as _paths_logger

    _paths_logger.warning(
        "⚠️ [SYSTEM] Aviso: A estrutura de diretórios não pôde ser verificada automaticamente: %s",
        e,
    )

# =========================================================
# UTILITÁRIOS PADRÃO DO SISTEMA
# =========================================================


def get_db_connection(db_path: Path) -> str:
    return str(db_path.resolve())


def next_project_dir() -> Path:
    """Retorna o próximo diretório de projeto (project01, project02, ...)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _RESULT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    counter = 0
    with open(_RESULT_LOCK_FILE, "w") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            if _RESULT_COUNTER_FILE.exists():
                try:
                    with open(_RESULT_COUNTER_FILE) as f:
                        data = json.load(f)
                        counter = data.get("counter", 0)
                except Exception:
                    counter = 0
            counter += 1
            with open(_RESULT_COUNTER_FILE, "w") as f:
                json.dump({"counter": counter}, f)
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

    project_name = f"project{counter:03d}"
    project_dir = RESULTS_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


_LANG_EXT = {
    "python": ".py",
    "py": ".py",
    "php": ".php",
    "html": ".html",
    "htm": ".html",
    "css": ".css",
    "javascript": ".js",
    "js": ".js",
    "node": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "java": ".java",
    "rust": ".rs",
    "rs": ".rs",
    "go": ".go",
    "golang": ".go",
    "ruby": ".rb",
    "rb": ".rb",
    "c": ".c",
    "c++": ".cpp",
    "cpp": ".cpp",
    "csharp": ".cs",
    "cs": ".cs",
    "swift": ".swift",
    "kotlin": ".kt",
    "kt": ".kt",
    "scala": ".scala",
    "perl": ".pl",
    "pl": ".pl",
    "r": ".r",
    "shell": ".sh",
    "bash": ".sh",
    "sh": ".sh",
    "sql": ".sql",
    "yaml": ".yaml",
    "yml": ".yaml",
    "json": ".json",
    "xml": ".xml",
    "markdown": ".md",
    "md": ".md",
    "dockerfile": ".dockerfile",
    "makefile": ".makefile",
    "aspx": ".aspx",
    "asp": ".aspx",
    "cshtml": ".cshtml",
    "razor": ".cshtml",
    "pdf": ".pdf",
    "documento": ".pdf",
}


def _detect_extension(code: str, task: str = "") -> str:
    code_stripped = code.strip()
    task_lower = task.lower()
    if code_stripped.startswith("```"):
        first_line = code_stripped.split("\n")[0].lstrip("`").strip()
        if first_line in ("python", "py"):
            return ".py"
        if first_line in ("html",):
            return ".html"
        if first_line in ("css",):
            return ".css"
        if first_line in ("javascript", "js"):
            return ".js"
        if first_line in ("php",):
            return ".php"
        code_stripped = "\n".join(code_stripped.split("\n")[1:])
        if code_stripped.endswith("```"):
            code_stripped = code_stripped[:-3]
        code_stripped = code_stripped.strip()
    if "<?php" in code_stripped:
        return ".php"
    if "<%@ Page" in code_stripped or "<%@" in code_stripped[:200]:
        return ".aspx"
    if code_stripped.startswith("<!DOCTYPE") or code_stripped.startswith("<html"):
        return ".html"
    if code_stripped.startswith("<?xml"):
        return ".xml"
    if code_stripped.startswith("{") and ":" in code_stripped[:100]:
        return ".json"
    if code_stripped.startswith("body {") or (
        code_stripped.startswith(".") and "{" in code_stripped[:100]
    ):
        return ".css"
    # PYTHON must be detected BEFORE pdf since fpdf code needs execution to generate binary PDF
    if (
        code_stripped.startswith("def ")
        or code_stripped.startswith("import ")
        or code_stripped.startswith("from ")
    ):
        return ".py"
    # PDF only if NOT executable code (documentation/markdown content)
    if "pdf" in task_lower or "documento" in task_lower:
        return ".pdf"
    if (
        code_stripped.startswith("function ")
        or code_stripped.startswith("const ")
        or code_stripped.startswith("let ")
        or code_stripped.startswith("var ")
    ):
        return ".js"
    if code_stripped.startswith("#include") or code_stripped.startswith("#ifndef"):
        return ".c"
    if code_stripped.startswith("#!/"):
        ext = (
            code_stripped.split("\n")[0].rsplit("/", 1)[-1]
            if "/" in code_stripped.split("\n")[0]
            else ""
        )
        return {"bash": ".sh", "python": ".py", "node": ".js", "php": ".php"}.get(
            ext, ".sh"
        )
    task_words = set(task_lower.split())
    for lang, ext in _LANG_EXT.items():
        if lang in task_words:
            return ext
    return ".txt"


def _safe_relative_path(base_dir: Path, user_path: str) -> Path:
    """Resolve *user_path* relativo a *base_dir* e bloqueia path traversal.

    Um `filepath` como ``"../../etc/passwd"`` é rejeitado porque o caminho
    resolvido estaria fora de *base_dir*.

    Raises:
        PermissionError: se o caminho resolvido escapar de *base_dir*.
    """
    base = base_dir.resolve()
    full = (base / user_path).resolve()
    try:
        full.relative_to(base)
    except ValueError:
        raise PermissionError(
            f"Path traversal bloqueado: '{user_path}' -> {full} (fora de {base})"
        )
    return full


def save_result_artifact(task: str, files: dict, code: str = "") -> Path:
    """Salva arquivos gerados no próximo diretório de projeto sequencial."""
    project_dir = next_project_dir()
    metadata = {
        "task": task,
        "timestamp": __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat(),
    }
    with open(project_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    for filepath, content in files.items():
        full_path = _safe_relative_path(project_dir, filepath)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
    if code and not files:
        ext = _detect_extension(code, task)
        output_name = f"output{ext}"
        output_path = project_dir / output_name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(code)
    return project_dir


def ensure_structure() -> None:
    """Garante que todos os diretórios críticos existam e coleta falhas em background."""
    _ensure_dirs()
    _run_failure_collection_in_background()


def _run_failure_collection_in_background():
    """Dispara coleta de falhas em thread separada para não travar o bootstrap."""
    import threading

    def _collect():
        try:
            from iaglobal.agents.failure_analysis_agent import FailureAnalysisAgent

            system_data = FailureAnalysisAgent.collect_system_data()
            if (
                system_data.get("errors", {}).get("total", 0) > 0
                or system_data.get("metrics", {}).get("total_calls", 0) > 0
            ):
                report = FailureAnalysisAgent.generate_report(system_data)
                FailureAnalysisAgent.persist_report(system_data, report)
        except Exception:
            pass

    t = threading.Thread(target=_collect, daemon=True, name="failure-collector")
    t.start()
