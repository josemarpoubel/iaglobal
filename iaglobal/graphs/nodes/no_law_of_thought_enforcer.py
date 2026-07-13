# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_law_of_thought_enforcer.py
"""Nó responsável por validar a presença do campo 'reasoning' no contexto.

Este nó aplica a Lei do Pensamento (Universal Law of Thinking) ao pipeline.
"""

from iaglobal.exceptions import LawViolation


async def run_law_of_thought_enforcer(ctx: dict) -> dict:
    """Valida a presença do campo 'reasoning' no contexto.

    Args:
        ctx (dict): Contexto de execução do pipeline.

    Returns:
        dict: Contexto inalterado se 'reasoning' estiver presente.

    Raises:
        LawViolation: Se o campo 'reasoning' não estiver presente no contexto.
    """
    if "reasoning" not in ctx:
        raise LawViolation("Lei do Pensamento: campo 'reasoning' obrigatório")
    return ctx
