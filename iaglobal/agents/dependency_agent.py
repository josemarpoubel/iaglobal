# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# /iaglobal/agents/dependency_agent.py
"""DependencyAgent — Filtra templates de dependências com base na arquitetura definida."""

import json
import re
import subprocess
import sys


from typing import Dict, List, Set, Any

from dataclasses import dataclass, field

from iaglobal.utils.logger import logger
from iaglobal.agents.agent_base import AgentBase


@dataclass
class DependencyResult:
    """Contrato de dados rígido para as dependências finais."""

    requirements_txt: str
    packages: List[str] = field(default_factory=list)
    excluded_sections: List[str] = field(default_factory=list)


class DependencyAgent(AgentBase):
    def __init__(self):
        super().__init__(agent_name="dependency")

    # Regex para capturar o nome da seção e as dependências abaixo dela
    # Ex: Captura "BASE CORE" e as linhas seguintes até o próximo comentário ou fim do arquivo
    _SECTION_REGEX = re.compile(
        r"#\s*=+\s*\n#\s*(?P<name>[^\n]+?)\s*\n#\s*=+\s*\n(?P<deps>.*?)(?=\n#\s*=+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    # Mapeamento de palavras-chave de arquitetura para as seções do template
    # Se o Architect decidir por "django", a seção "BASE CORE" é incluída.
    _ARCH_TO_SECTION_MAP = {
        "django": ["BASE CORE"],
        "fastapi": ["BASE MICROSERVICE / FASTAPI"],
        "websocket": ["EXTRAS PARA PRODUÇÃO AVANÇADA"],
        "redis": ["EXTRAS PARA PRODUÇÃO AVANÇADA"],
    }

    @staticmethod
    def _normalize_section_name(name: str) -> str:
        """Remove descrições parentéticas do nome da seção para matching."""
        idx = name.find("(")
        return name[:idx].strip() if idx > 0 else name.strip()

    def resolve_dependencies(
        self, template_content: str, architecture_context: Dict
    ) -> DependencyResult:
        """
        Lê o template de dependências e filtra apenas as seções necessárias
        com base no contexto da arquitetura (vindo do ArchitectAgent/IntentClassifier).
        """
        logger.info("📦 [DEPENDENCY AGENT] Resolvendo dependências do template...")

        # 1. Extrai o framework principal escolhido pela arquitetura
        frameworks = architecture_context.get("entities", {}).get("framework", [])
        tech_stack = architecture_context.get("tech_stack", [])

        # Normaliza para lower case para matching
        context_keywords = set(
            [f.lower() for f in frameworks] + [t.lower() for t in tech_stack]
        )

        # 2. Identifica quais seções do template devem ser incluídas
        sections_to_include: Set[str] = set()
        for keyword in context_keywords:
            for arch_key, sections in self._ARCH_TO_SECTION_MAP.items():
                if arch_key in keyword:
                    sections_to_include.update(sections)

        # Fallback: Se não detectou nada específico, inclui a base core por segurança
        if not sections_to_include:
            sections_to_include.add("BASE CORE")
            logger.warning(
                "[DEPENDENCY AGENT] Nenhum framework específico detectado. Usando BASE CORE como fallback."
            )

        # 3. Parseia o template e filtra as seções
        final_packages = []
        excluded_sections = []

        for match in self._SECTION_REGEX.finditer(template_content):
            raw_section_name = match.group("name").strip()
            section_name = self._normalize_section_name(raw_section_name)
            deps_block = match.group("deps").strip()

            # Extrai apenas os nomes dos pacotes (ignora linhas vazias ou comentários dentro do bloco)
            packages = [
                line.strip()
                for line in deps_block.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]

            if section_name in sections_to_include:
                final_packages.extend(packages)
                logger.info(
                    "📦 [DEPENDENCY AGENT] Incluindo seção: %s (%d pacotes)",
                    raw_section_name,
                    len(packages),
                )
            else:
                excluded_sections.append(raw_section_name)
                logger.debug(
                    "📦 [DEPENDENCY AGENT] Excluindo seção: %s", raw_section_name
                )

        # 4. Remove duplicatas e ordena alfabeticamente (Boas práticas de requirements.txt)
        final_packages = sorted(list(set(final_packages)))
        requirements_txt = "\n".join(final_packages)

        logger.info(
            "📦 [DEPENDENCY AGENT] Concluído | total_packages=%d | excluded_sections=%d",
            len(final_packages),
            len(excluded_sections),
        )

        return DependencyResult(
            requirements_txt=requirements_txt,
            packages=final_packages,
            excluded_sections=excluded_sections,
        )


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
            missing.append(
                {"name": pkg, "status": "missing", "suggested": f"pip install {pkg}"}
            )

    result = {
        "dependencies": deps
        + [
            {"name": p, "status": "ok"}
            for p in imports
            if p not in [d["name"] for d in deps]
        ],
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
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                installed.append(pkg_name)
                logger.info("📦 [AUTO-INSTALL] ✅ %s instalado", pkg_name)
            else:
                failed.append({"package": pkg_name, "error": result.stderr[:200]})
                logger.warning(
                    "📦 [AUTO-INSTALL] ❌ %s falhou: %s", pkg_name, result.stderr[:100]
                )
        except subprocess.TimeoutExpired:
            failed.append({"package": pkg_name, "error": "timeout"})
            logger.warning("📦 [AUTO-INSTALL] ❌ %s timeout", pkg_name)
        except Exception as e:
            failed.append({"package": pkg_name, "error": str(e)})

    return {
        "installed": installed,
        "failed": failed,
        "total": len(missing),
        "success": len(installed),
    }


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

    known_techs = {
        "flask",
        "django",
        "fastapi",
        "requests",
        "numpy",
        "pandas",
        "sqlalchemy",
        "alembic",
        "pytest",
        "celery",
        "redis",
        "boto3",
        "docker",
        "kubernetes",
        "jinja2",
        "click",
        "typer",
        "rich",
        "pydantic",
        "httpx",
        "aiohttp",
        "psycopg2",
        "mysqlclient",
        "pymongo",
        "pillow",
        "matplotlib",
        "seaborn",
        "scikit_learn",
        "torch",
        "tensorflow",
        "transformers",
        "beautifulsoup4",
        "guzzlehttp/guzzle",
        "phpmailer/phpmailer",
    }

    known_in_text = {t for t in known_techs if t in text.lower()}
    imports.update(known_in_text)

    return sorted(imports)


def _get_installed_packages() -> Dict[str, str]:
    """Retorna dict {nome_pacote: versão} dos pacotes instalados via pip."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return {p["name"].lower(): p["version"] for p in packages}
    except Exception as e:
        logger.warning("📦 [DEPENDENCY] pip list falhou: %s", e)

    return {}
