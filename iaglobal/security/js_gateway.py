# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""JSGateway — single entry point para parsing de JavaScript no iaglobal.

Mesmo padrão do ASTGateway (Python): um único ponto no sistema que sabe
parsear JS, sem subprocess, sem regex, sem shell-out para node. Usa
tree-sitter com a gramática tree-sitter-javascript — parser real C com
binding Python, tolerante a erro (sempre produz árvore, marcando nós
problemáticos em vez de só explodir exceção).

Rationale para tree-sitter vs alternativas:
- `node --check` via subprocess = precisa de Node no runtime (dependência
  de ambiente, não só de dev), e viola a diretriz do projeto contra
  chamadas diretas ao SO.
- `esprima`/`pyjsparser` (pure Python) estão estagnados — sem optional
  chaining `?.`, nullish coalescing `??`, top-level await.
- tree-sitter é mantido, é o parser por trás de GitHub code navigation,
  Neovim e Zed, e dá o mesmo retorno estruturado que ASTGateway: bool
  valid + lista de erros com linha/coluna.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any

try:
    from tree_sitter import Language, Parser, Tree, Node
    import tree_sitter_javascript as tsjs

    _JS_LANGUAGE = Language(tsjs.language())
    _JS_PARSER = Parser(_JS_LANGUAGE)
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    _TREE_SITTER_AVAILABLE = False


@dataclass
class JSParseResult:
    """Resultado de parsing de JS — mesma forma que ASTResult."""

    valid: bool
    tree: Optional[Any] = None
    errors: List[str] = field(default_factory=list)
    error_line: Optional[int] = None
    error_column: Optional[int] = None


class JSGateway:
    """Único ponto do sistema onde parsing de JavaScript é permitido."""

    def parse(self, code: str) -> JSParseResult:
        if not _TREE_SITTER_AVAILABLE:
            return JSParseResult(
                valid=False,
                errors=["tree-sitter-javascript nao instalado"],
            )

        if not code or not code.strip():
            return JSParseResult(valid=False, errors=["Empty code"])

        try:
            tree: Tree = _JS_PARSER.parse(code.encode("utf-8"))
        except Exception as e:
            return JSParseResult(valid=False, errors=[f"parser error: {e}"])

        if not tree.root_node.has_error:
            return JSParseResult(valid=True, tree=tree)

        errors: List[str] = []
        first_line: Optional[int] = None
        first_col: Optional[int] = None

        def _walk(node: Node) -> None:
            nonlocal first_line, first_col
            if node.type == "ERROR" or node.is_missing:
                line, col = node.start_point
                if first_line is None:
                    first_line = line + 1
                    first_col = col + 1
                tag = "missing" if node.is_missing else "ERROR"
                errors.append(f"{tag} at line {line + 1}, column {col + 1}")
            for child in node.children:
                _walk(child)

        _walk(tree.root_node)
        return JSParseResult(
            valid=False,
            tree=tree,
            errors=errors,
            error_line=first_line,
            error_column=first_col,
        )
