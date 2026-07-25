# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ArtifactKind(str, Enum):
    CODE = "code"
    HTML = "html"
    MARKDOWN = "markdown"
    ERROR = "error"
    DOCUMENTATION = "documentation"
    JSON = "json"
    TEXT = "text"
    EMPTY = "empty"
    UNKNOWN = "unknown"


@dataclass
class GeneratedArtifact:
    content: str
    kind: ArtifactKind = ArtifactKind.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_str(cls, text: str) -> "GeneratedArtifact":
        if not text or not text.strip():
            return cls(content="", kind=ArtifactKind.EMPTY)

        stripped = text.lstrip()

        if stripped.startswith("```"):
            return cls(content=text, kind=ArtifactKind.MARKDOWN)

        if stripped.startswith(("{", "[", '"')):
            return cls(content=text, kind=ArtifactKind.JSON)

        if stripped.startswith("<"):
            if stripped.startswith(("<!DOCTYPE", "<html")):
                return cls(content=text, kind=ArtifactKind.HTML)
            return cls(content=text, kind=ArtifactKind.HTML)

        code_indicators = (
            "def ", "class ", "import ", "from ", "async def ", "await ",
            "function ", "const ", "let ", "var ", "export ", "public ",
            "private ", "protected ", "static ", "interface ", "type ",
            "SELECT ", "INSERT ", "CREATE ", "ALTER ", "DROP ",
            "print(", "print ", "return ", "if ", "for ", "while ",
            "try:", "except", "with ", "lambda ", "yield ", "raise ",
        )
        if any(stripped.startswith(kw) for kw in code_indicators):
            return cls(content=text, kind=ArtifactKind.CODE)

        if stripped.startswith(("# ", "##", "---")):
            return cls(content=text, kind=ArtifactKind.MARKDOWN)

        if len(stripped.split()) > 10 and not any(c.isdigit() for c in stripped[:20]):
            return cls(content=text, kind=ArtifactKind.TEXT)

        return cls(content=text, kind=ArtifactKind.UNKNOWN)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "kind": self.kind.value,
            "metadata": self.metadata,
        }