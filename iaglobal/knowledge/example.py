# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Example Intelligence — exemplos de código verificados como fonte de contexto.

Um CodeExample é um snippet de código real que foi verificado (compila/importa)
e pode ser usado como contexto para o LLM em vez de geração do zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from iaglobal.knowledge.contracts import ValidationResult, KnowledgeProvenance


@dataclass(frozen=True)
class CodeExample:
    technology: str
    api: str
    code: str
    language: str = "python"
    description: str = ""
    validated: bool = False
    validation: ValidationResult | None = None
    provenance: KnowledgeProvenance | None = None
    tags: frozenset[str] = frozenset()

    @property
    def is_verified(self) -> bool:
        return self.validated and (self.validation is None or self.validation.success)


@dataclass
class ExampleLibrary:
    _examples: dict[str, list[CodeExample]] = field(default_factory=dict)

    def add(self, example: CodeExample) -> None:
        key = f"{example.technology}:{example.api}"
        self._examples.setdefault(key, []).append(example)

    def get(self, technology: str, api: str) -> list[CodeExample]:
        return self._examples.get(f"{technology}:{api}", [])

    def for_technology(self, technology: str) -> list[CodeExample]:
        return [
            ex
            for key, examples in self._examples.items()
            for ex in examples
            if key.startswith(f"{technology}:")
        ]
