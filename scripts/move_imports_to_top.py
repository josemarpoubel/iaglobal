#!/usr/bin/env python3
"""
move_imports_to_top.py — Move imports module-level para o topo do arquivo.

Estratégia:
  1. Identifica o "prelúdio" do arquivo na ordem canônica:
       - comentários/linhas vazias (ex.: lineage marker)
       - docstring (uma linha ou multi-linha)
       - comentários/linhas vazias
       - `from __future__` e imports module-level consecutivos
     Esse prelúdio é preservado intacto e na ordem.
  2. Percorre o restante do arquivo em busca de imports module-level
     (linhas sem indentação, incl. multiline `from x import (`),
     remove-os do lugar e os reinsere ao final do bloco de imports do
     prelúdio.
  3. Só grava se o resultado compila e mudou.

Depois rode:  ruff check <files> --select=E402 --fix

Uso: python scripts/move_imports_to_top.py FILE [FILE ...]
"""
from __future__ import annotations

import sys
from pathlib import Path


def _is_import_start(line: str) -> bool:
    """True se a linha (sem indentação) inicia um import module-level."""
    if line[:1] in (" ", "\t"):
        return False
    stripped = line.strip()
    return stripped.startswith("import ") or stripped.startswith("from ")


def _collect_statement(lines: list[str], i: int) -> tuple[list[str], int]:
    """Coleta um statement completo, cuidando de parênteses/colchetes.

    Retorna (linhas do statement, próximo índice).
    """
    block: list[str] = []
    depth = 0
    j = i
    while j < len(lines):
        line = lines[j]
        block.append(line)
        depth += line.count("(") + line.count("[") + line.count("{")
        depth -= line.count(")") + line.count("]") + line.count("}")
        j += 1
        if depth <= 0:
            break
    return block, j


def _skip_blank_and_comments(lines: list[str], idx: int) -> int:
    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
        else:
            break
    return idx


def _skip_docstring(lines: list[str], idx: int) -> int:
    """Pula docstring que começa em `idx`. Retorna próximo índice."""
    stripped = lines[idx].strip()
    if not (stripped.startswith('"""') or stripped.startswith("'''")):
        return idx
    quote = stripped[:3]
    if stripped.count(quote) >= 2:  # docstring de uma linha
        return idx + 1
    j = idx + 1
    while j < len(lines) and quote not in lines[j]:
        j += 1
    return j + 1 if j < len(lines) else j


def find_preamble_end(lines: list[str]) -> int:
    """Índice (exclusive) do fim do prelúdio (imports + cabeçalho)."""
    idx = _skip_blank_and_comments(lines, 0)
    idx = _skip_docstring(lines, idx)
    idx = _skip_blank_and_comments(lines, idx)

    start = idx
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("from __future__"):
            idx += 1
            continue
        if _is_import_start(line):
            _, idx = _collect_statement(lines, idx)
            continue
        break
    return idx if idx > start else start


def process_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    pre_end = find_preamble_end(lines)
    if pre_end == 0:
        return False

    # Percorre a região "meio/fim" em busca de imports module-level.
    # Rastreia strings triplas para NÃO mover imports que são conteúdo
    # de templates (ex.: f\"\"\"...import sys...\"\"\" rodado em subprocesso).
    moved: list[str] = []
    removed: set[int] = set()
    i = pre_end
    in_triple = False
    triple_quote = ""
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Alterna estado de string tripla
        if not in_triple:
            m = re.search(r'(f|r|b|u|fr|rf|F|R|B|U|FR|RF)?("""|\'\'\')', stripped)
            if m:
                triple_quote = m.group(2)
                if stripped.count(triple_quote) < 2:
                    in_triple = True
                # se abriu e fechou na mesma linha, segue normal
                i += 1
                continue
        else:
            if triple_quote in line:
                in_triple = False
            i += 1
            continue

        if _is_import_start(line):
            block, i = _collect_statement(lines, i)
            removed.update(range(i - len(block), i))
            moved.extend(block)
        else:
            i += 1

    if not moved:
        return False

    moved_joined = "".join(moved)
    if not moved_joined.endswith("\n"):
        moved_joined += "\n"

    body = [line for i, line in enumerate(lines) if i not in removed]

    new_lines = list(lines[:pre_end])
    if moved_joined.strip():
        new_lines.append(moved_joined)
        if body[pre_end:]:
            next_line = body[pre_end]
            if next_line.strip():
                new_lines.append("\n")
    new_lines.extend(body[pre_end:])

    new_content = "".join(new_lines)

    try:
        compile(new_content, str(path), "exec")
    except SyntaxError as e:
        print(f"  SKIP {path}: compile SyntaxError: {e}")
        return False

    if new_content != original:
        path.write_text(new_content, encoding="utf-8")
        print(f"  FIXED {path}")
        return True
    return False


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: move_imports_to_top.py FILE [FILE ...]")
        return 1
    changed = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"  MISSING {path}")
            continue
        if process_file(path):
            changed += 1
    print(f"\n{changed} file(s) changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
