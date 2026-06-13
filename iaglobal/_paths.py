# iaglobal/_paths.py 

import json
import os

from pathlib import Path

#/iaglobal/memory/data$ tree
#.
#├── cache
#├── logs
#├── memory_backups
#├── provider_metrics
#├── result
#├── script
#├── snapshots
#├── storage
#├── temp
#└── work

# =========================================================
# ROOT DO SISTEMA (SOURCE OF TRUTH)
# =========================================================

# Raiz do pacote iaglobal (onde _paths.py está)
PACKAGE_DIR = Path(__file__).resolve().parent

# Raiz do projeto (onde pyproject.toml, docs/, cli.py estão)
PROJECT_ROOT = PACKAGE_DIR.parent

# =========================================================
# DATA LAYER (SEMPRE DENTRO DO PACOTE iaglobal)
# =========================================================

DATA_ROOT = PACKAGE_DIR / "memory" / "data"

# Subdiretórios organizados
JSON_DIR = DATA_ROOT / "json"

DB_DIR = DATA_ROOT / "db"

CBOR2_DIR = DATA_ROOT / "cbor2"

MEMORY_DIR = DATA_ROOT

BACKUP_DIR = DATA_ROOT / "memory_backups"

CACHE_DIR = DATA_ROOT / "cache"

LOG_DIR = DATA_ROOT / "logs"

SCRIPTS_DIR = DATA_ROOT / "script"

TEMP_DIR = DATA_ROOT / "temp"

# =========================================================
# RESULT OUTPUT (projetos numerados sequencialmente)
# =========================================================

RESULTS_DIR = DATA_ROOT / "result"

_RESULT_COUNTER_FILE = RESULTS_DIR / ".counter.json"

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

ERROR_LOG = JSON_DIR / "errors.json"

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
    """
    Garante estrutura mínima do sistema antes de qualquer execução.
    Isso elimina erro de path em runtime.
    """
    critical_dirs = [
        DATA_ROOT, MEMORY_DIR, JSON_DIR, DB_DIR, CBOR2_DIR, 
        BACKUP_DIR, CACHE_DIR, LOG_DIR, DOCS_DIR, SCRIPTS_DIR, 
        TEMP_DIR, RESULTS_DIR, SNAPSHOTS_DIR, WORK_DIR, 
        PROVIDER_METRICS_DIR, IMAGES_DIR, MONITORED_DIR, 
        DOCS_TEMP_DIR, SANDBOX_DIR,
    ]

    for d in critical_dirs:
        d.mkdir(parents=True, exist_ok=True)

# bootstrap automático com proteção para evitar falhas silenciosas na importação
try:
    _ensure_dirs()
except Exception as e:
    # Registra o erro, mas permite que o fluxo de execução prossiga 
    # para que o Bootstrap possa tratar a falha de forma adequada
    print(f"⚠️ [SYSTEM] Aviso: A estrutura de diretórios não pôde ser verificada automaticamente: {e}")

# =========================================================
# UTILITÁRIOS PADRÃO DO SISTEMA
# =========================================================

def get_db_connection(db_path: Path) -> str:
    """
    Normaliza caminhos para SQLite e engines externas.
    """
    return str(db_path.resolve())


def resolve_path(path: Path | str) -> str:
    """
    Resolve qualquer path para absoluto seguro.
    """
    return str(Path(path).expanduser().resolve())


def next_project_dir() -> Path:
    """Retorna o próximo diretório de projeto (project01, project02, ...)."""
    import json
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    counter = 0
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
    project_name = f"project{counter:03d}"
    project_dir = RESULTS_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


_LANG_EXT = {
    "python": ".py", "py": ".py",
    "php": ".php",
    "html": ".html", "htm": ".html",
    "css": ".css",
    "javascript": ".js", "js": ".js", "node": ".js",
    "typescript": ".ts", "ts": ".ts",
    "java": ".java",
    "rust": ".rs", "rs": ".rs",
    "go": ".go", "golang": ".go",
    "ruby": ".rb", "rb": ".rb",
    "c": ".c", "c++": ".cpp", "cpp": ".cpp", "csharp": ".cs", "cs": ".cs",
    "swift": ".swift",
    "kotlin": ".kt", "kt": ".kt",
    "scala": ".scala",
    "perl": ".pl", "pl": ".pl",
    "r": ".r",
    "shell": ".sh", "bash": ".sh", "sh": ".sh",
    "sql": ".sql",
    "yaml": ".yaml", "yml": ".yaml",
    "json": ".json",
    "xml": ".xml",
    "markdown": ".md", "md": ".md",
    "dockerfile": ".dockerfile",
    "makefile": ".makefile",
    "aspx": ".aspx", "asp": ".aspx",
    "cshtml": ".cshtml", "razor": ".cshtml",
    "pdf": ".pdf", "documento": ".pdf",
}


def _detect_extension(code: str, task: str = "") -> str:
    code_stripped = code.strip()
    task_lower = task.lower()
    # Remove markdown fences antes de detectar
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
    if code_stripped.startswith("body {") or (code_stripped.startswith(".") and "{" in code_stripped[:100]):
        return ".css"
    if code_stripped.startswith("def ") or code_stripped.startswith("import ") or code_stripped.startswith("from "):
        return ".py"
    if code_stripped.startswith("function ") or code_stripped.startswith("const ") or code_stripped.startswith("let ") or code_stripped.startswith("var "):
        return ".js"
    if code_stripped.startswith("#include") or code_stripped.startswith("#ifndef"):
        return ".c"
    if code_stripped.startswith("#!/"):
        ext = code_stripped.split("\n")[0].rsplit("/", 1)[-1] if "/" in code_stripped.split("\n")[0] else ""
        return {"bash": ".sh", "python": ".py", "node": ".js", "php": ".php"}.get(ext, ".sh")

    if "pdf" in task_lower or "documento" in task_lower:
        return ".pdf"

    # Fallback: palavras-chave da task
    task_words = set(task_lower.split())
    for lang, ext in _LANG_EXT.items():
        if lang in task_words:
            return ext

    return ".txt"


def save_result_artifact(task: str, files: dict, code: str = "") -> Path:
    """Salva arquivos gerados no próximo diretório de projeto sequencial."""
    project_dir = next_project_dir()
    metadata = {
        "task": task,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    with open(project_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    for filepath, content in files.items():
        full_path = project_dir / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
    if code and not files:
        ext = _detect_extension(code, task)
        output_name = f"output{ext}"
        with open(project_dir / output_name, "w") as f:
            f.write(code)
    return project_dir

# iaglobal/_paths.py
# Função pública ensure_structure — delega para _ensure_dirs completa
ensure_structure = _ensure_dirs
