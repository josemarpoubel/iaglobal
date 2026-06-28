def _validar_integracoes(resultado, integracoes: Dict[str, Set[str]]) -> None:
    """Valida se todas as dependências registradas no INTEGRATION_REGISTRY estão satisfeitas."""
    from pathlib import Path
    from typing import Dict, Set
    import logging
    logger = logging.getLogger(__name__)

    for modulo, dependencias in integracoes.items():
        modulo_path = Path("/home/kitohamachi/projeto-iaglobal") / modulo
        if not modulo_path.exists():
            logger.warning(f"Módulo registrado não encontrado: {modulo}")
            continue

        # Verificar se todas as dependências são chamadas pelo menos uma vez
        for dep in dependencias:
            dep_path = Path("/home/kitohamachi/projeto-iaglobal") / dep
            
            # Verificar chamadas diretas
            chamadas_encontradas = set()
            for origem, destinos in resultado.chamadas.items():
                if dep_path.name.replace(".py", "") in origem or dep in origem:
                    chamadas_encontradas.update(destinos)
            
            # Verificar imports explícitos
            if not chamadas_encontradas:
                with open(modulo_path, "r") as f:
                    content = f.read()
                    if f"from {dep.replace('.py', '').replace('/', '.')}" in content:
                        chamadas_encontradas.add("import")
            
            if not chamadas_encontradas:
                logger.warning(f"Dependência não satisfeita: {modulo} → {dep}")

    # Adicionar ENTRY_POINTS ao conjunto de funções não órfãs
    from iaglobal.integration_registry import ENTRY_POINTS
    resultado.refs_callback.update(ENTRY_POINTS)