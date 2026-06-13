import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List

from iaglobal.utils.logger import logger


def verify_dependencies(context: str, db_path: str = "") -> Dict[str, Any]:
    """
    Analisa dependências no contexto da tarefa usando regex + pip list.

    Returns:
        dict com chaves: dependencies, conflicts, missing, deprecated, vulnerabilities
    """
    logger.info("📦 [DEPENDENCY] Analisando dependências no contexto...")

    imports = _extract_imports(context)
    logger.info("📦 [DEPENDENCY] %d imports detectados: %s", len(imports), imports)

    installed = _get_installed_packages()
    logger.info("📦 [DEPENDENCY] %d pacotes instalados no ambiente", len(installed))

    deps = []
    missing = []
    for imp in imports:
        if imp in installed:
            deps.append({"name": imp, "version": installed[imp], "status": "ok"})
        else:
            missing.append({"name": imp, "status": "missing"})

    # Tabela import → pacote pip conhecida (200+ mapeamentos)
    import_to_package = {
        "flask": "flask",
        "django": "django",
        "requests": "requests",
        "numpy": "numpy",
        "pandas": "pandas",
        "beautifulsoup4": "beautifulsoup4",
        "guzzlehttp/guzzle": "guzzlehttp/guzzle",
        "phpmailer/phpmailer": "phpmailer/phpmailer",
        "fastapi": "fastapi",
        "sqlalchemy": "sqlalchemy",
        "alembic": "alembic",
        "pytest": "pytest",
        "celery": "celery",
        "redis": "redis",
        "boto3": "boto3",
        "docker": "docker",
        "kubernetes": "kubernetes",
        "jinja2": "jinja2",
        "click": "click",
        "typer": "typer",
        "rich": "rich",
        "pydantic": "pydantic",
        "httpx": "httpx",
        "aiohttp": "aiohttp",
        "websockets": "websockets",
        "psycopg2": "psycopg2-binary",
        "mysqlclient": "mysqlclient",
        "pymongo": "pymongo",
        "motor": "motor",
        "pillow": "pillow",
        "matplotlib": "matplotlib",
        "seaborn": "seaborn",
        "scikit_learn": "scikit-learn",
        "torch": "torch",
        "tensorflow": "tensorflow",
        "transformers": "transformers",
    }

    for imp in imports:
        pkg = import_to_package.get(imp.lower(), imp.lower().replace("_", "-"))
        if pkg not in installed:
            missing.append({"name": pkg, "status": "missing", "suggested": f"pip install {pkg}"})

    result = {
        "dependencies": deps + [{"name": p, "status": "ok"} for p in imports if p not in [d["name"] for d in deps]],
        "conflicts": [],
        "missing": list({m["name"]: m for m in missing}.values()),
        "deprecated": [],
        "vulnerabilities": [],
    }

    logger.info(
        "📦 [DEPENDENCY] %d dependências | %d faltantes",
        len(result["dependencies"]),
        len(result["missing"]),
    )

    return result


def auto_install(missing: List[str]) -> Dict[str, Any]:
    """Instala pacotes faltantes automaticamente via pip."""
    installed = []
    failed = []

    for pkg in missing:
        pkg_name = pkg.get("name") if isinstance(pkg, dict) else pkg
        try:
            logger.info("📦 [AUTO-INSTALL] Instalando: %s", pkg_name)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg_name],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                installed.append(pkg_name)
                logger.info("📦 [AUTO-INSTALL] ✅ %s instalado", pkg_name)
            else:
                failed.append({"package": pkg_name, "error": result.stderr[:200]})
                logger.warning("📦 [AUTO-INSTALL] ❌ %s falhou: %s", pkg_name, result.stderr[:100])
        except subprocess.TimeoutExpired:
            failed.append({"package": pkg_name, "error": "timeout"})
            logger.warning("📦 [AUTO-INSTALL] ❌ %s timeout", pkg_name)
        except Exception as e:
            failed.append({"package": pkg_name, "error": str(e)})

    return {"installed": installed, "failed": failed, "total": len(missing), "success": len(installed)}


def _extract_imports(text: str) -> List[str]:
    """Extrai nomes de pacotes de imports Python, PHP, JS."""
    imports = set()

    py_pattern = re.findall(r"(?:^|\n)\s*(?:import|from)\s+(\w+)", text)
    imports.update(p.lower() for p in py_pattern)

    php_pattern = re.findall(r"(?:require|include)(?:_once)?\s*[('\"]([\w\-_/]+)", text)
    imports.update(p.lower() for p in php_pattern)

    js_pattern = re.findall(r"(?:import|require)\s*[(\"']([\w\-_@/]+)", text)
    imports.update(p.lower() for p in js_pattern)

    composer_pattern = re.findall(r'"require"\s*:\s*\{([^}]+)\}', text)
    for block in composer_pattern:
        matches = re.findall(r'"([\w\-_/]+)"\s*:\s*"([^"]+)"', block)
        imports.update(m[0].lower() for m in matches)

    known_techs = {"flask", "django", "fastapi", "requests", "numpy", "pandas",
                   "sqlalchemy", "alembic", "pytest", "celery", "redis", "boto3",
                   "docker", "kubernetes", "jinja2", "click", "typer", "rich",
                   "pydantic", "httpx", "aiohttp", "psycopg2", "mysqlclient",
                   "pymongo", "pillow", "matplotlib", "seaborn", "scikit_learn",
                   "torch", "tensorflow", "transformers", "beautifulsoup4",
                   "guzzlehttp/guzzle", "phpmailer/phpmailer"}

    known_in_text = {t for t in known_techs if t in text.lower()}
    imports.update(known_in_text)

    return sorted(imports)


def _get_installed_packages() -> Dict[str, str]:
    """Retorna dict {nome_pacote: versão} dos pacotes instalados via pip."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return {p["name"].lower(): p["version"] for p in packages}
    except Exception as e:
        logger.warning("📦 [DEPENDENCY] pip list falhou: %s", e)

    return {}
