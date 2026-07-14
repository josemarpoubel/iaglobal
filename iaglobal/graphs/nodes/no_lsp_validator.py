# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
LSP Validator Node — Validação estática de código como um Language Server.

Usa pyflakes para detectar:
  - Erros de sintaxe
  - Imports não utilizados
  - Nomes indefinidos
  - Redefinições de nomes
  - Outros erros semânticos comuns

Saída: lista de diagnósticos estilo LSP (line, column, message, severity).
"""

import time
from typing import Dict, Any, List

from iaglobal.utils.logger import get_logger
from iaglobal.security.ast_gateway import ASTGateway

logger = get_logger("iaglobal.graphs.nodes.lsp_validator")

# Gateway singleton para AST parsing
_ast_gateway = ASTGateway()


def _validar_com_pyflakes(code: str) -> List[Dict[str, Any]]:
    """Executa pyflakes no código e retorna diagnósticos estilo LSP."""
    diagnostics = []
    try:
        import pyflakes.api
        import pyflakes.messages
        import pyflakes.checker

        class LSPReporter:
            def __init__(self):
                self.diagnostics = []

            def unexpectedError(self, filename, msg):
                self.diagnostics.append(
                    {
                        "line": 1,
                        "column": 0,
                        "message": f"Erro inesperado: {msg}",
                        "severity": 1,
                        "source": "pyflakes",
                    }
                )

            def syntaxError(self, filename, msg, lineno, offset, text):
                self.diagnostics.append(
                    {
                        "line": lineno or 1,
                        "column": offset or 0,
                        "message": f"Erro de sintaxe: {msg}",
                        "severity": 1,
                        "source": "pyflakes",
                        "text": text or "",
                    }
                )

            def flake(self, msg):
                line = getattr(msg, "lineno", 1)
                col = getattr(msg, "col", 0)
                severity = (
                    2
                    if any(
                        k in msg.__class__.__name__
                        for k in (
                            "UndefinedName",
                            "UndefinedExport",
                            "UndefinedLocal",
                            "DuplicateArgument",
                            "LateFutureImport",
                        )
                    )
                    else 3
                )
                self.diagnostics.append(
                    {
                        "line": line,
                        "column": col,
                        "message": str(msg),
                        "severity": severity,
                        "source": "pyflakes",
                        "type": msg.__class__.__name__,
                    }
                )

        reporter = LSPReporter()
        pyflakes.api.check(code, "<iaglobal_lsp>", reporter)
        diagnostics = reporter.diagnostics
    except ImportError:
        logger.warning("[LSP] pyflakes não disponível — pulando validação avançada")
    except Exception as e:
        logger.warning("[LSP] Erro ao executar pyflakes: %s", e)
    return diagnostics


def _validar_imports(code: str) -> List[Dict[str, Any]]:
    """Verifica se os imports do código resolvem no ambiente atual."""
    diagnostics = []
    try:
        result = _ast_gateway.parse(code)
        if not result.valid or result.tree is None:
            return diagnostics
        
        tree = result.tree
        import ast
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    try:
                        __import__(alias.name)
                    except ImportError:
                        diagnostics.append(
                            {
                                "line": getattr(node, "lineno", 1),
                                "column": 0,
                                "message": f"Import não encontrado: '{alias.name}'",
                                "severity": 1,
                                "source": "lsp_imports",
                            }
                        )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                names = [alias.name for alias in node.names]
                try:
                    if module_name:
                        mod = __import__(module_name, fromlist=names)
                        for name in names:
                            if name and not hasattr(mod, name):
                                diagnostics.append(
                                    {
                                        "line": getattr(node, "lineno", 1),
                                        "column": 0,
                                        "message": f"'{name}' não encontrado em '{module_name}'",
                                        "severity": 2,
                                        "source": "lsp_imports",
                                    }
                                )
                except ImportError:
                    diagnostics.append(
                        {
                            "line": getattr(node, "lineno", 1),
                            "column": 0,
                            "message": f"Módulo não encontrado: '{module_name}'",
                            "severity": 1,
                            "source": "lsp_imports",
                        }
                    )
    except SyntaxError:
        pass  # pyflakes já capturou
    return diagnostics


async def run_lsp_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida o código gerado com análise estática LSP-like.

    Pipeline:
      1. Extrai código das memórias (coder/multi_coder)
      2. Executa pyflakes (sintaxe + semântica)
      3. Verifica imports no ambiente atual
      4. Retorna diagnósticos + decisão (commit/retry/rollback)
    """
    start = time.time()
    resolved_model = "lsp_validator"

    memory = ctx.get("memory", {})
    code = ""

    # Tenta múltiplas fontes: memória do DAG, contextos dos builders, e generated_code
    sources = (
        "multi_coder",
        "coder",
        "debug_coder",
        "backend_builder",
        "frontend_builder",
        "api_builder",
        "database_builder",
    )
    for source in sources:
        artifact = memory.get(source, {})
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if isinstance(artifact, dict):
            for key in ("output", "code", "content", "integrated_code"):
                val = artifact.get(key)
                if val and isinstance(val, str) and val.strip():
                    code = val
                    break
            if code:
                break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    # Fallback: generated_code diretamente no ctx
    if not code:
        code = ctx.get("generated_code", "") or str(
            ctx.get("input", {}).get("task", "")
        )

    if not code:
        logger.warning("[LSP] Nenhum código encontrado para validar.")
        return {
            "output": "",
            "diagnostics": [],
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": (time.time() - start) * 1000.0,
                "cost": 0.0,
            },
        }

    # Fase 1 — pyflakes (sintaxe + semântica)
    pyflakes_diags = _validar_com_pyflakes(code)

    # Fase 2 — verificação de imports
    import_diags = _validar_imports(code)

    all_diagnostics = pyflakes_diags + import_diags
    errors = [d for d in all_diagnostics if d.get("severity") == 1]
    warnings = [d for d in all_diagnostics if d.get("severity", 3) <= 2]
    has_syntax_error = any(
        "Erro de sintaxe" in d.get("message", "") for d in all_diagnostics
    )
    has_import_error = any(d.get("source") == "lsp_imports" for d in all_diagnostics)

    success = len(errors) == 0
    latency = (time.time() - start) * 1000.0

    logger.info(
        "[LSP] Validação concluída | erros=%d warnings=%d success=%s | latency=%.1fms",
        len(errors),
        len(warnings),
        success,
        latency,
    )
    if errors:
        for e in errors[:5]:
            logger.warning("[LSP]   Linha %(line)d: %(message)s", e)

    return {
        "output": code,
        "diagnostics": all_diagnostics,
        "lsp_valid": success,
        "lsp_errors": [d["message"] for d in errors],
        "execution_metrics": {
            "model": resolved_model,
            "success": success,
            "latency": latency,
            "cost": 0.0,
        },
    }
