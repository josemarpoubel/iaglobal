"""ErrorCapture — Captura automática de exceções para o Subconsciente.

Intercepta erros em agentes e registra automaticamente no Curto Prazo
(02_Short_Term) do vault Obsidian, para serem processados no próximo
Ciclo do Sono (REMSleepEngine).
"""
from datetime import datetime, UTC

import functools
import sys
import traceback
from typing import Optional, List

from iaglobal.obsidian.subconsciousapi import SubconsciousAPI


class ErrorCapture:
    """Capturador de erros que registra falhas no subconsciente.

    Pode ser usado como context manager ou decorator para capturar
    exceções automaticamente.
    """

    def __init__(self, vault_path=None, agente: str = "unknown"):
        self.subconscious = SubconsciousAPI(vault_path)
        self.agente = agente

    def capturar(self, tarefa: str, erro: Exception,
                 tags: Optional[List[str]] = None) -> str:
        """Captura uma exceção e registra no curto prazo do Obsidian.

        Returns:
            Nome do arquivo de erro criado.
        """
        tb_str = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))
        caminho = self.subconscious.registrar_erro(
            agente=self.agente,
            tarefa=tarefa,
            erro=tb_str,
            tags=tags,
        )
        return caminho.stem

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            tb_str = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            self.subconscious.registrar_erro(
                agente=self.agente,
                tarefa="context_manager_capture",
                erro=tb_str,
                tags=["#erro-capturado"],
            )
        return False


def capturar_erro_subconsciente(agente: str = "unknown", tags: Optional[List[str]] = None):
    """Decorator que captura exceções de uma função e registra no subconsciente.

    Uso:
        @capturar_erro_subconsciente(agente="meu_agente")
        def minha_funcao():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            capture = ErrorCapture(agente=agente)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                capture.capturar(tarefa=func.__name__, erro=e, tags=tags)
                # Lei da Caridade: enriquece o erro com contexto sem alterar seu tipo
                e.args = (f"[{agente}] Erro em {func.__name__}: {e}",)
                raise
        return wrapper
    return decorator
