# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
AutoCorrectionLoop — Loop de auto-verificação e correção para agentes.

Filosofia:
  Após gerar código, cada agente deve "ler como se fosse um compilador":
  detectar variáveis não definidas, funções chamadas sem escopo, erros
  de sintaxe — e corrigir antes de entregar o resultado final.

  Usa apenas ferramentas locais (pyflakes, ast, esprima, Jedi).
  Zero chamadas LLM. Zero custo de inferência.
"""

import re
import ast
import time
import hashlib
import asyncio
from dataclasses import dataclass, field
from typing import List, Tuple, Set, Dict, Any, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.security.ast_gateway import ASTGateway

logger = get_logger("iaglobal.core.auto_correction")

# Gateway singleton para AST parsing
_ast_gateway = ASTGateway()

# Limiar de reincidencia antes da apoptose contratual
REINCIDENCIA_LIMIAR = 3


@dataclass
class Correcao:
    """Resultado de uma iteração de auto-correção."""

    issues: List[str] = field(default_factory=list)
    fixes_aplicados: List[str] = field(default_factory=list)
    codigo_final: str = ""
    foi_corrigido: bool = False
    linguagem: str = "unknown"


class _SanitizerTransformer(ast.NodeTransformer):
    """Substitui nós ofensivos por alternativas seguras."""

    def __init__(self, violations: List[Dict[str, Any]]):
        self.violation_lines: Set[int] = {v["line"] for v in violations if v["line"]}
        self.sanitized: List[str] = []

    def visit_Import(self, node: ast.Import) -> Any:
        if node.lineno in self.violation_lines:
            self.sanitized.append(f"L{node.lineno}: Import removido por segurança")
            return ast.Pass()
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.lineno in self.violation_lines:
            self.sanitized.append(f"L{node.lineno}: ImportFrom removido por segurança")
            return ast.Pass()
        return node

    def visit_Call(self, node: ast.Call) -> Any:
        if node.lineno in self.violation_lines:
            if isinstance(node.func, ast.Name) and node.func.id in {
                "eval",
                "exec",
                "compile",
                "__import__",
                "getattr",
                "setattr",
                "delattr",
                "globals",
                "vars",
                "dir",
            }:
                self.sanitized.append(
                    f"L{node.lineno}: Chamada '{node.func.id}()' substituída por None"
                )
                return ast.Constant(value=None)
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "system",
                "popen",
                "spawn",
                "execute",
            }:
                self.sanitized.append(
                    f"L{node.lineno}: Acesso a '.{node.func.attr}()' substituído por None"
                )
                return ast.Constant(value=None)
        return self.generic_visit(node)


class AutoCorrectionLoop:
    """
    Loop de auto-correção que valida e repara código localmente.

    Fluxo:
      1. Detecta linguagem (Python, JS/JSX, HTML)
      2. Executa validação com ferramentas nativas
      3. Aplica correções heurísticas
      4. Re-valida
      5. Repete até MAX_ITERATIONS ou código válido
    """

    MAX_ITERATIONS = 3
    _violation_counter: Dict[str, int] = {}  # agent_name -> count (memória only)

    def corrigir(self, codigo: str, task: str = "", agent_name: str = "") -> Correcao:
        """Executa o loop completo de auto-correção.

        Args:
            codigo: Código fonte para validar/corrigir
            task: Descrição da tarefa (contexto)
            agent_name: Nome do agente que gerou o código (para rastreio de reincidência)

        Returns:
            Correcao com resultado da validação
        """
        if not codigo or not codigo.strip():
            return Correcao(issues=["Código vazio"], codigo_final=codigo)

        start = time.time()
        issues_encontradas: List[str] = []
        fixes_aplicados: List[str] = []
        linguagem = self._detectar_linguagem(codigo)

        codigo_atual = codigo
        for i in range(self.MAX_ITERATIONS):
            issues, fixes = self._validar_e_corrigir(codigo_atual, linguagem)

            if issues:
                issues_encontradas.extend(issues)
                fixes_aplicados.extend(fixes)
                logger.info(
                    "[AUTO-CORRECAO] Iteracao %d/%d | issues=%d fixes=%d | lang=%s",
                    i + 1,
                    self.MAX_ITERATIONS,
                    len(issues),
                    len(fixes),
                    linguagem,
                )

            if fixes:
                codigo_atual = self._aplicar_fixes(codigo_atual, fixes, linguagem)

            if not issues:
                break

        foi_corrigido = codigo_atual != codigo or bool(fixes_aplicados)
        latency = (time.time() - start) * 1000.0

        # Rastreio de reincidência de violações de segurança
        sec_issues = [i for i in issues_encontradas if i.startswith("SECURITY:")]
        if sec_issues and agent_name:
            self._reportar_violacao_seguranca(agent_name, sec_issues)

        if foi_corrigido:
            logger.info(
                "[AUTO-CORRECAO] Finalizado | issues=%d fixes=%d lang=%s latency=%.1fms",
                len(issues_encontradas),
                len(fixes_aplicados),
                linguagem,
                latency,
            )
        else:
            logger.info(
                "[AUTO-CORRECAO] Código limpo | lang=%s latency=%.1fms",
                linguagem,
                latency,
            )

        return Correcao(
            issues=issues_encontradas,
            fixes_aplicados=fixes_aplicados,
            codigo_final=codigo_atual,
            foi_corrigido=foi_corrigido,
            linguagem=linguagem,
        )

    def _reportar_violacao_seguranca(
        self, agent_name: str, violacoes: List[str]
    ) -> None:
        """Registra violação de segurança e dispara apoptose se reincidente."""
        # Contador de reincidência em memória
        self._violation_counter[agent_name] = (
            self._violation_counter.get(agent_name, 0) + 1
        )
        reincidencia = self._violation_counter[agent_name]

        logger.warning(
            "[AUTO-CORRECAO] 🛡️ Violacao seguranca: %s | agente=%s | reincidencia=%d/%d",
            violacoes[0][:80],
            agent_name,
            reincidencia,
            REINCIDENCIA_LIMIAR,
        )

        # Registro persistente via EpigeneticRegistry (assíncrono, fire-and-forget)
        try:
            from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry

            registry = EpigeneticRegistry()
            detalhes = {"violacoes": violacoes, "reincidencia": reincidencia}
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    registry.record_failure(
                        agent_name,
                        hashlib.sha256(str(violacoes).encode()).hexdigest()[:12],
                        "ast_violation",
                        detalhes,
                    )
                )
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("[AUTO-CORRECAO] EpigeneticRegistry indisponivel: %s", e)

        # Se reincidência >= limiar, dispara apoptose contratual via OmniMind
        if reincidencia >= REINCIDENCIA_LIMIAR:
            try:
                from iaglobal.obsidian.omnimind import OmniMind

                omnimind = OmniMind()
                duracao = 24 if reincidencia < 6 else None  # 24h ou permanente
                omnimind.emitir_gatilho_apoptose(
                    agent_id=agent_name,
                    motivo=(
                        f"Reincidencia de seguranca AST ({reincidencia}x): "
                        f"{violacoes[0][:100]}"
                    ),
                    duration_hours=duracao,
                    violation_type="ast_violation",
                )
            except Exception as e:
                logger.warning("[AUTO-CORRECAO] Falha ao emitir apoptose: %s", e)

    def _detectar_linguagem(self, codigo: str) -> str:
        """Detecta se o código é Python, JS/JSX ou outro."""
        if not codigo:
            return "unknown"

        # Usar ASTGateway em vez de ast.parse direto
        result = _ast_gateway.parse(codigo)
        if result.valid:
            return "python"

        try:
            from iaglobal.validation.js_validator import detect_lang

            lang = detect_lang(codigo)
            if lang in ("js", "jsx", "ts"):
                return lang
        except ImportError:
            pass
        if re.search(r"<html|<!DOCTYPE|<\w+\s+[^>]*>", codigo[:500]):
            return "html"
        return "unknown"

    def _validar_e_corrigir(
        self, codigo: str, linguagem: str
    ) -> Tuple[List[str], List[str]]:
        """
        Valida o código e retorna (issues, fixes).
        Cada fix é uma tupla (tipo, detalhe) para aplicação posterior.
        """
        issues = []
        fixes = []

        if linguagem == "python":
            py_issues, py_fixes = self._validar_python(codigo)
            issues.extend(py_issues)
            fixes.extend(py_fixes)

        elif linguagem in ("js", "jsx"):
            js_issues, js_fixes = self._validar_js(codigo, linguagem)
            issues.extend(js_issues)
            fixes.extend(js_fixes)

        elif linguagem == "html":
            if codigo.count("</") != codigo.count("<"):
                issues.append("Tags HTML possivelmente desbalanceadas")

        return issues, fixes

    def _validar_python(self, codigo: str) -> Tuple[List[str], List[str]]:
        """Valida Python com ASTGateway + pyflakes, retorna issues e fixes."""
        issues = []
        fixes = []

        result = _ast_gateway.parse(codigo)

        # Sanitização de violações de segurança (AST)
        if not result.valid and result.metadata:
            transformer = _SanitizerTransformer(result.metadata)
            try:
                tree_sanitized = transformer.visit(result.tree)
                ast.fix_missing_locations(tree_sanitized)
                codigo_sanitizado = ast.unparse(tree_sanitized)
                result = _ast_gateway.parse(codigo_sanitizado)
                if result.valid:
                    fixes.append(("substituir_codigo", codigo_sanitizado))
                    for s in transformer.sanitized:
                        issues.append(f"SECURITY: {s}")
                    logger.info(
                        "[AUTO-CORRECAO] Sanitizacao AST: %d violacoes removidas",
                        len(transformer.sanitized),
                    )
                else:
                    issues.append(
                        "SECURITY: Violações detectadas mas sanitização falhou"
                    )
            except Exception as e:
                logger.warning("[AUTO-CORRECAO] Erro na sanitizacao AST: %s", e)
                issues.append(f"SECURITY: Erro ao sanitizar ({e})")
            return issues, fixes

        if not result.valid:
            if result.errors:
                error_msg = result.errors[0].strip("'\"")
                # Extrair informações do erro
                import re

                match = re.search(r"line (\d+)", error_msg)
                line = int(match.group(1)) if match else 0
                msg = f"SyntaxError: {error_msg} (linha {line})"
                issues.append(msg)
                fixes.append(("fechar_brackets", msg))
            return issues, fixes

        try:
            from pyflakes.api import check
            from pyflakes.reporter import Reporter as BaseReporter

            class _CaptureReporter(BaseReporter):
                def __init__(s):
                    s.errors = []

                def syntaxError(s, filename, msg, lineno, offset, text):
                    s.errors.append(f"L{lineno}: {msg}")

                def flake(s, msg):
                    s.errors.append(str(msg))

            rep = _CaptureReporter()
            check(codigo, "<auto_correction>", rep)
            for err in rep.errors:
                issues.append(err)
                if "undefined name" in err.lower():
                    nome = err.split("'")[1] if "'" in err else ""
                    if nome:
                        fixes.append(("stub_var", nome))
                elif "undefined variable" in err.lower():
                    nome = err.split("'")[1] if "'" in err else ""
                    if nome:
                        fixes.append(("stub_var", nome))
                elif "imported but unused" in err.lower():
                    pass
        except ImportError:
            logger.debug("[AUTO-CORRECAO] pyflakes indisponivel")

        return issues, fixes

    def _validar_js(self, codigo: str, lang: str) -> Tuple[List[str], List[str]]:
        """Valida JS/JSX com esprima."""
        issues = []
        fixes = []

        try:
            import esprima

            source_type = (
                "module" if "import " in codigo or "export " in codigo else "script"
            )
            options = {"jsx": lang == "jsx"}
            if source_type == "module":
                esprima.parseModule(codigo, options)
            else:
                esprima.parseScript(codigo, options)
        except Exception as e:
            msg = str(e).split("\n")[0][:120]
            issues.append(f"JSError: {msg}")
            if "Unexpected end of input" in msg:
                fixes.append(("fechar_brackets", msg))
            elif "Unexpected token ILLEGAL" in msg:
                fixes.append(("fechar_string", msg))

        return issues, fixes

    def _aplicar_fixes(self, codigo: str, fixes: List[str], linguagem: str) -> str:
        """Aplica a lista de correções heurísticas ao código."""
        codigo_atual = codigo

        for fix in fixes:
            tipo = fix[0] if isinstance(fix, tuple) else fix
            detalhe = fix[1] if isinstance(fix, tuple) and len(fix) > 1 else ""

            if tipo == "substituir_codigo" and detalhe:
                codigo_atual = detalhe
            elif tipo == "fechar_brackets":
                codigo_atual = self._fechar_brackets(codigo_atual)
            elif tipo == "fechar_string":
                codigo_atual = self._fechar_strings(codigo_atual)
            elif tipo == "stub_var" and detalhe:
                codigo_atual = self._adicionar_stub(codigo_atual, detalhe)
            elif tipo == "sanitizado":
                pass

        return codigo_atual

    def _fechar_brackets(self, codigo: str) -> str:
        """Fecha brackets/parênteses/chaves não fechados."""
        try:
            from iaglobal.validation.js_validator import (
                _close_unclosed_brackets as _js_close,
            )

            return _js_close(codigo)
        except ImportError:
            pass
        stack = []
        pairs = {")": "(", "]": "[", "}": "{"}
        for ch in codigo:
            if ch in "([{":
                stack.append(ch)
            elif ch in ")]}":
                if stack and stack[-1] == pairs[ch]:
                    stack.pop()
        if not stack:
            return codigo
        open_to_close = {"(": ")", "[": "]", "{": "}"}
        closing = "".join(open_to_close[ch] for ch in reversed(stack))
        return codigo.rstrip() + "\n" + closing

    def _fechar_strings(self, codigo: str) -> str:
        """Fecha strings não fechadas."""
        try:
            from iaglobal.validation.js_validator import _close_unclosed_strings

            return _close_unclosed_strings(codigo)
        except ImportError:
            pass
        for ch in "\"'`":
            if codigo.count(ch) % 2 != 0:
                return codigo.rstrip() + ch
        return codigo

    def _adicionar_stub(self, codigo: str, nome_var: str) -> str:
        """Adiciona stub para variável não definida."""
        linhas = codigo.split("\n")
        stub = f"{nome_var} = None  # auto-stub para variavel indefinida"
        if linhas and linhas[-1].strip():
            linhas.append(stub)
        else:
            linhas.insert(len(linhas) - 1, stub)
        logger.info("[AUTO-CORRECAO] Stub adicionado: %s = None", nome_var)
        return "\n".join(linhas)


auto_correction = AutoCorrectionLoop()
