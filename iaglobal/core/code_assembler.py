"""
code_assembler.py — Monta código válido a partir de blocos extraídos da web.

Metáfora biológica:
  - CodeBlock = aminoácido (unidade funcional isolada)
  - CodeAssembler = ribossomo (sintetiza proteína/código funcional a partir dos aa)
  - Validação AST = dobramento proteico (verifica estrutura 3D antes de liberar)
"""
import ast
import re
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field

from iaglobal.search.search_code_extractor import CodeBlock

logger = logging.getLogger("iaglobal")

DEFAULT_HEAD = """    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aplicacao</title>"""

HTML_SKELETON = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    {head_extra}
    <style>
    {styles}
    </style>
</head>
<body>
    {body_content}
    <script>
    {scripts}
    </script>
</body>
</html>"""


@dataclass
class AssemblyResult:
    code: str = ""
    language: str = ""
    blocks_used: int = 0
    blocks_total: int = 0
    valid: bool = False
    errors: List[str] = field(default_factory=list)


class CodeAssembler:
    """Monta código válido a partir de CodeBlocks extraídos da web."""

    def assemble(self, blocks: List[CodeBlock], language: str = "html") -> AssemblyResult:
        """Monta o melhor arquivo possível dos blocos disponíveis."""
        if not blocks:
            return AssemblyResult(errors=["Nenhum bloco de código disponível"])

        result = AssemblyResult(language=language, blocks_total=len(blocks))
        lang_blocks = [b for b in blocks if b.language == language]

        if language == "html":
            return self._assemble_html(blocks, result)
        elif language in ("python", "py"):
            return self._assemble_python(lang_blocks or blocks, result)
        elif language in ("css",):
            return self._assemble_css(blocks, result)
        elif language in ("javascript", "js"):
            return self._assemble_javascript(lang_blocks or blocks, result)
        else:
            best = max(blocks, key=lambda b: (b.confidence, b.line_count))
            result.code = best.code
            result.blocks_used = 1
            result.valid = len(best.code) > 10
            return result

    def _assemble_html(self, blocks: List[CodeBlock], result: AssemblyResult) -> AssemblyResult:
        """Monta HTML válido a partir de blocos mistos."""
        from iaglobal.search.search_code_extractor import SearchCodeExtractor

        html_blocks = [b for b in blocks if b.language == "html"]
        extractor = SearchCodeExtractor()
        components = extractor.extract_html_components(html_blocks)

        body_parts = list(components["body"])
        style_parts = list(components["style"])
        script_parts = list(components["script"])
        head_parts = list(components["head"])

        for block in blocks:
            if block.language == "css":
                style_parts.append(block.code)
            elif block.language in ("javascript", "js"):
                script_parts.append(block.code)

        body_content = "\n    ".join(body_parts) if body_parts else "<div id='app'>Conteudo</div>"
        styles = "\n    ".join(style_parts) if style_parts else "body { font-family: sans-serif; margin: 20px; }"
        scripts = "\n    ".join(script_parts) if script_parts else "// app logic"
        if head_parts:
            best_head = max(head_parts, key=len)
            deduped_head = []
            seen_head_tags: set = set()
            for tag in re.findall(r"<[^>]+>", best_head):
                tag_normalized = re.sub(r'\s+', ' ', tag.lower()).strip()
                if tag_normalized not in seen_head_tags:
                    seen_head_tags.add(tag_normalized)
                    deduped_head.append(tag)
            head_extra = "\n    ".join(deduped_head) if deduped_head else DEFAULT_HEAD
        else:
            head_extra = DEFAULT_HEAD

        code = HTML_SKELETON.format(
            head_extra=head_extra,
            styles=styles,
            body_content=body_content,
            scripts=scripts,
        )

        result.code = code
        result.blocks_used = len(body_parts) + len(style_parts) + len(script_parts) + len(head_parts)
        result.valid = bool(re.search(r"<!DOCTYPE html>", code, re.IGNORECASE))
        if not result.valid:
            result.errors.append("HTML sem DOCTYPE — estrutura inválida")
        return result

    def _assemble_python(self, blocks: List[CodeBlock], result: AssemblyResult) -> AssemblyResult:
        """Monta Python válido a partir de blocos — valida cada um via AST."""
        valid_parts: List[str] = []
        for block in blocks:
            code = block.code.strip()
            if not code:
                continue
            try:
                tree = ast.parse(code)
                if self._has_meaningful_content(tree):
                    valid_parts.append(code)
            except SyntaxError:
                pass

        if not valid_parts:
            result.errors.append("Nenhum bloco Python sintaticamente válido")
            return result

        merged = self._dedupe_and_merge(valid_parts)
        try:
            ast.parse(merged)
            result.code = merged
            result.valid = True
            result.blocks_used = len(valid_parts)
        except SyntaxError as e:
            result.code = valid_parts[0]
            try:
                ast.parse(result.code)
                result.valid = True
                result.blocks_used = 1
            except SyntaxError:
                result.errors.append(f"AST inválido mesmo após merge: {e}")

        return result

    def _assemble_css(self, blocks: List[CodeBlock], result: AssemblyResult) -> AssemblyResult:
        """Monta CSS a partir de blocos — deduplica seletores."""
        seen_rules: set = set()
        rules: List[str] = []
        for block in blocks:
            for rule_match in re.finditer(
                r"([^{]+)\{([^}]+)\}", block.code
            ):
                selector = rule_match.group(1).strip()
                body = rule_match.group(2).strip()
                key = f"{selector}{{{body}}}"
                if key not in seen_rules:
                    seen_rules.add(key)
                    rules.append(f"{selector} {{\n    {body}\n}}")

        if not rules:
            result.errors.append("Nenhuma regra CSS extraída")
            return result

        merged = "\n\n".join(rules)
        if not merged.strip():
            merged = "/* CSS assembler from search snippets */"

        result.code = merged
        result.valid = True
        result.blocks_used = len(rules)
        return result

    def _assemble_javascript(self, blocks: List[CodeBlock], result: AssemblyResult) -> AssemblyResult:
        """Monta JavaScript — concatenacão com validação básica."""
        valid_parts: List[str] = []
        for block in blocks:
            code = block.code.strip()
            if not code:
                continue
            try:
                from iaglobal.search.search_code_extractor import _check_js_syntax
                _check_js_syntax(code)
                valid_parts.append(code)
            except SyntaxError:
                continue

        if not valid_parts:
            result.errors.append("Nenhum bloco JS válido")
            return result

        merged = "\n\n".join(valid_parts)
        try:
            from iaglobal.search.search_code_extractor import _check_js_syntax
            _check_js_syntax(merged)
            result.code = merged
            result.valid = True
            result.blocks_used = len(valid_parts)
        except SyntaxError:
            result.code = valid_parts[0]
            result.valid = True
            result.blocks_used = 1

        return result

    def _dedupe_and_merge(self, parts: List[str]) -> str:
        """Deduplica e merge de blocos Python, preservando imports no topo."""
        imports: List[str] = []
        functions: List[str] = []
        classes: List[str] = []
        other: List[str] = []
        seen_imports: set = set()
        seen_funcs: set = set()
        seen_classes: set = set()

        for part in parts:
            try:
                tree = ast.parse(part)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name not in seen_imports:
                                seen_imports.add(alias.name)
                                imports.append(f"import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        names = [n.name for n in node.names]
                        key = f"from {module} import {', '.join(names)}"
                        if key not in seen_imports:
                            seen_imports.add(key)
                            imports.append(key)
                    elif isinstance(node, ast.FunctionDef):
                        if node.name not in seen_funcs:
                            seen_funcs.add(node.name)
                            start = node.lineno - 1
                            end = node.end_lineno or start
                            lines = part.splitlines()[start:end]
                            functions.append("\n".join(lines))
                    elif isinstance(node, ast.ClassDef):
                        if node.name not in seen_classes:
                            seen_classes.add(node.name)
                            start = node.lineno - 1
                            end = node.end_lineno or start
                            lines = part.splitlines()[start:end]
                            classes.append("\n".join(lines))
            except SyntaxError:
                other.append(part)

        merged_lines: List[str] = []
        merged_lines.extend(imports)
        if imports:
            merged_lines.append("")
        merged_lines.extend(classes)
        if classes:
            merged_lines.append("")
        merged_lines.extend(functions)
        if functions:
            merged_lines.append("")
        merged_lines.extend(other)
        return "\n".join(merged_lines)

    @staticmethod
    def _has_meaningful_content(tree: ast.AST) -> bool:
        """Verifica se a AST tem conteúdo além de imports/docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return True
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Module):
                continue
            return True
        return False
