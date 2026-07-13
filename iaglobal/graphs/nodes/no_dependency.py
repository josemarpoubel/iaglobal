# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Dependency handler — resolve template de dependencias por arquitetura e verifica instalacao."""

import time
import os
import logging
from pathlib import Path
from typing import Dict, Any

from iaglobal.agents.dependency_agent import (
    DependencyAgent,
    DependencyResult,
    auto_install,
    verify_dependencies,
)

logger = logging.getLogger(__name__)

_DEPENDENCY_AGENT = DependencyAgent()


def _load_requirements_template(project_root: str = "") -> str:
    """Carrega o template requirements.txt do projeto."""
    paths_to_try = [
        Path(project_root) / "requirements.txt" if project_root else None,
        Path.cwd() / "requirements.txt",
        Path(__file__).resolve().parent.parent.parent.parent / "requirements.txt",
    ]
    for p in filter(None, paths_to_try):
        if p and p.exists():
            return p.read_text(encoding="utf-8")
    return ""


async def run_dependency(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))
    context = memory.get("coder", {}).get("output", "") or task

    # 1. Resolve template de dependencias baseado no contexto de arquitetura
    architecture_context = (
        memory.get("technology_selection", {}).get("output", {})
        or memory.get("architect", {}).get("output", {})
        or {}
    )
    template = _load_requirements_template(
        project_root=ctx.get("working_directory", "")
    )
    resolved: DependencyResult | None = None
    if template:
        resolved = _DEPENDENCY_AGENT.resolve_dependencies(
            template, architecture_context
        )
        logger.info(
            "[DEPENDENCY] Template resolvido: %d pacotes, %d secoes excluidas",
            len(resolved.packages) if resolved else 0,
            len(resolved.excluded_sections) if resolved else 0,
        )

    # 2. Verifica dependencias instaladas vs imports do codigo
    result = verify_dependencies(context=context)
    missing = result.get("missing", [])

    # 3. Auto-instala se configurado
    install_result = None
    if missing and os.getenv("IAGLOBAL_AUTO_INSTALL_DEPENDENCIES", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        install_result = auto_install(missing)

    logger.info(
        "[DEPENDENCY] %d dependencias, %d ausentes, auto_install=%s",
        len(result.get("dependencies", [])),
        len(missing),
        bool(install_result),
    )

    return {
        **ctx,
        "output": result,
        "dependencies": result,
        "template_resolved": {
            "requirements_txt": resolved.requirements_txt if resolved else "",
            "packages": resolved.packages if resolved else [],
            "excluded_sections": resolved.excluded_sections if resolved else [],
        }
        if resolved
        else None,
        "missing": missing,
        "auto_install": install_result,
        "execution_metrics": {
            "success": True,
            "latency": time.time() - start,
            "cost": 0.0,
            "model": "local",
        },
    }
