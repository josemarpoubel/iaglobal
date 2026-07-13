# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Template loader para skills iaglobal.

Carrega automaticamente os templates de prompt da pasta templates/
e os associa às skills correspondentes.

Uso:
    from iaglobal.evolution.skills.template_loader import load_skill_template

    template = load_skill_template("coder")
    # Retorna: "Como desenvolvedor sênior..."

    # Ou com fallback:
    template = load_skill_template("skill_inexistente", default="Template genérico: {task}")
"""

from pathlib import Path
from typing import Optional
from functools import lru_cache

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.skills.template_loader")

# Caminho absoluto para a pasta de templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


@lru_cache(maxsize=128)
def load_skill_template(skill_name: str, default: str = "") -> str:
    """Carrega template de uma skill específica.

    Args:
        skill_name: Nome da skill (ex: "coder", "critic", "planner")
        default: Template fallback se arquivo não existir

    Returns:
        Conteúdo do template ou default se não encontrado

    Exemplo:
        >>> load_skill_template("coder")
        "Como desenvolvedor sênior especializado em Python..."

        >>> load_skill_template("inexistente", default="Use {task}")
        "Use {task}"
    """
    # Normaliza nome: remove prefixo "skill_" e sufixo "_agent"
    normalized = skill_name.lower().replace("skill_", "").replace("_agent", "")

    # Tenta encontrar o arquivo de template
    template_file = TEMPLATES_DIR / f"{normalized}.txt"

    if template_file.exists():
        try:
            content = template_file.read_text(encoding="utf-8").strip()
            logger.debug(
                f"[TEMPLATE] Carregado: {normalized}.txt ({len(content)} chars)"
            )
            return content
        except Exception as e:
            logger.error(f"[TEMPLATE] Erro ao ler {template_file}: {e}")
            return default

    # Se não encontrou com nome normalizado, tenta com nome completo
    if normalized != skill_name.lower():
        template_file_alt = TEMPLATES_DIR / f"{skill_name.lower()}.txt"
        if template_file_alt.exists():
            try:
                content = template_file_alt.read_text(encoding="utf-8").strip()
                logger.debug(
                    f"[TEMPLATE] Carregado: {skill_name.lower()}.txt ({len(content)} chars)"
                )
                return content
            except Exception as e:
                logger.error(f"[TEMPLATE] Erro ao ler {template_file_alt}: {e}")

    # Cache miss registrado
    logger.debug(f"[TEMPLATE] Não encontrado: {normalized}.txt — usando default")
    return default


def get_available_templates() -> list:
    """Retorna lista de templates disponíveis na pasta."""
    if not TEMPLATES_DIR.exists():
        return []

    templates = []
    for f in TEMPLATES_DIR.glob("*.txt"):
        if f.is_file():
            templates.append(f.stem)

    return sorted(templates)


def validate_template(skill_name: str) -> tuple:
    """Valida se um template tem placeholders válidos.

    Args:
        skill_name: Nome da skill para validar

    Returns:
        Tuple (valid, placeholders, message)
        - valid: True se template é válido
        - placeholders: Lista de placeholders encontrados
        - message: Mensagem de erro ou sucesso
    """
    template = load_skill_template(skill_name)

    if not template:
        return (False, [], "Template vazio ou não encontrado")

    # Extrai placeholders {variavel}
    import re

    placeholders = re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", template)

    if not placeholders:
        return (False, [], "Template sem placeholders — será usado como texto fixo")

    # Placeholders comuns esperados
    common_placeholders = {
        "task",
        "refined_task",
        "plan",
        "requirements",
        "business_rules",
        "architect",
        "code",
        "execution_plan",
        "technology_selection",
        "domain_model",
    }

    # Verifica se há placeholders desconhecidos
    unknown = set(placeholders) - common_placeholders
    if unknown:
        logger.warning(
            f"[TEMPLATE] Placeholders desconhecidos em {skill_name}: {unknown}"
        )

    return (
        True,
        sorted(set(placeholders)),
        f"Template válido com {len(set(placeholders))} placeholders",
    )
