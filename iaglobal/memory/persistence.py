# iaglobal/memory/persistence.py

import json

from typing import Any, Optional
from iaglobal.memory.memory_storage import storage


class Persistence:
    """Interface unificada de persistência com suporte a argumentos legados."""

    def __init__(self, *args, **kwargs):
        # Ignora argumentos antigos (como storage_path) que causavam o erro
        self.db = storage

    def save_json(self, name: str, data: Any):
        """Adapter: Grava JSON serializado como string no banco central."""
        return self.db.store(name, str(data))

    def load_json(self, name: str) -> Optional[Any]:
        """Adapter: Recupera dados do banco central."""
        return self.db.retrieve(name)

    @staticmethod
    def validar_integridade_memoria(dados: Any) -> bool:
        """Validação de compatibilidade legada."""
        return isinstance(dados, list)

    def get_context_for_llm(self, task: str) -> str:
        """Busca o sucesso e retorna uma string formatada em JSON para o prompt."""
        data = self.db.retrieve(task)
        if data:
            # Garante que o retorno para o modelo seja um JSON string limpo
            return json.dumps(data, indent=2, ensure_ascii=False)
        return "{}"


# Instância Singleton mantendo compatibilidade em todo o sistema
persistence = Persistence()
