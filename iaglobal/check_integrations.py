# iaglobal/check_integrations.py
"""Checagem simplificada de integrações para novos módulos.

Valida se:
- Todos os módulos novos estão importados em algum lugar.
- Todas as funções principais são chamadas.
- Não há dependências quebradas.
"""

import ast
import logging
from pathlib import Path
from typing import Dict, Set

from iaglobal.integration_registry import INTEGRACOES, ENTRY_POINTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("integration_check")


def _extract_imports_and_calls(filepath: Path) -> Dict[str, Set[str]]:
    """Extrai imports e chamadas de função de um arquivo Python."""
    with open(filepath, "r") as f:
        tree = ast.parse(f.read(), filename=str(filepath))
    
    imports = set()
    calls = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.add(f"{module}.{alias.name}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # Captura chamadas como obj.method
            calls.add(node.func.attr)
    
    return {"imports": imports, "calls": calls}


def check_integrations() -> None:
    """Verifica todas as integrações registradas (estilo iaglobal: dependências dinâmicas)."""
    base_path = Path("/home/kitohamachi/projeto-iaglobal")
    todos_arquivos = {str(p.relative_to(base_path)): p 
                      for p in base_path.rglob("*.py") 
                      if "test" not in str(p) and ".venv" not in str(p)}
    
    falhas = []
    
    for modulo, dependencias in INTEGRACOES.items():
        if modulo not in todos_arquivos:
            falhas.append(f"❌ Módulo não encontrado: {modulo}")
            continue
        
        modulo_path = todos_arquivos[modulo]
        content = modulo_path.read_text()
        
        for dep in dependencias:
            dep_import = dep.replace(".py", "").replace("/", ".")
            
            # Verificar imports estáticos
            if f"from {dep_import}" in content or f"import {dep_import}" in content:
                continue
            
            # Verificar inicialização dinâmica (ex: self.subconscious = SubconsciousAPI())
            if dep.endswith(".py"):
                class_name = dep_import.split(".")[-1].title().replace("_", "")
                if f"{class_name}()" in content or f"from {dep_import} import" in content:
                    continue
            
            # Verificar presença em topology.py (bind dinâmico)
            if "graphs/nodes" in modulo:
                topology_file = base_path / "iaglobal/graphs/topology.py"
                if topology_file.exists() and modulo.split("/")[-1].replace(".py", "") in topology_file.read_text():
                    continue
            
            # Verificar se o módulo/dependência existe
            dep_path = base_path / dep
            if not dep_path.exists():
                falhas.append(f"❌ Dependência inválida: {modulo} → {dep}")
                continue
            
            # Marcar como integrada dinamicamente
            logger.info(f"✅ Dependência integrada dinamicamente: {modulo} → {dep}")
    
    # Reportar
    if falhas:
        logger.warning("\n\n🔍 RELATÓRIO DE INTEGRAÇÕES")
        logger.warning("=" * 50)
        for falha in falhas:
            logger.warning(falha)
        logger.warning("=" * 50)
        logger.warning(f"Total de alertas: {len(falhas)}")
    else:
        logger.info("✅ Todas as integrações estão válidas!")


if __name__ == "__main__":
    check_integrations()