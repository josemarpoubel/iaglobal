# iaglobal/graphs/contracts/node_contract.py
"""
NodeContract — Validação de contexto de entrada para nós do DAG.

Cada nó declara `required_inputs` — chaves que precisam existir em
ctx["memory"] com output válido antes de executar.

Se faltar alguma dependência, o nó NÃO executa silenciosamente:
- Levanta MissingContextError
- O ExecutionGraph pode capturar e aplicar RecoveryPolicy
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


class MissingContextError(RuntimeError):
    def __init__(self, node: str, missing: List[str]):
        self.node = node
        self.missing = missing
        super().__init__(f"Nó '{node}' requer inputs faltando: {missing}")


@dataclass
class NodeContract:
    required_inputs: List[str] = field(default_factory=list)
    optional_inputs: List[str] = field(default_factory=list)

    def validate(self, node_name: str, memory: Dict[str, Any]) -> None:
        missing = []
        for key in self.required_inputs:
            entry = memory.get(key, {})
            if isinstance(entry, dict):
                output = (
                    entry.get("output")
                    or entry.get("code")
                    or entry.get("built_prompt")
                    or ""
                )
                if not output or (isinstance(output, str) and len(output.strip()) < 5):
                    missing.append(key)
            elif not entry:
                missing.append(key)
        if missing:
            raise MissingContextError(node_name, missing)
