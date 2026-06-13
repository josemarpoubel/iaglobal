"""
IAGlobal v3 - Node: integrator
- Nó compartilhado usado pra consolidar saidas de nós paralelos e rotear pro reviewer
- Parte da phase quality (7 nós)
- Handler stub agora integra com novo nodes registry e builder
"""

from typing import Dict, Any



async def run_integrator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Integrator: consolidates parallel node outputs and normalizes for reviewer.

    Imediatamente após test_generator e sibling nodes; prepara inputs pra reviewer.
    """
    # stub
    out = {**ctx}
    return out


# manter chamado antigo por compatibilidade BELOW se necessário
# def integrate_pipeline_nodes() -> None:
#     ...
