# test_audit_path_sovereignty.py

#!/usr/bin/env python3
"""
audit_path_sovereignty.py

Verifica se modulos do pacote iaglobal respeitam o contrato de
soberania de dados definido em iaglobal/_paths.py.

Duas camadas de deteccao:

  1. Padroes conhecidos (Path(__file__).parent / "memory",
     PACKAGE_DIR / "memory", Path(*ROOT) / "iaglobal", os.path.join
     com "memory"/"data") -- da um rotulo especifico do padrao.

  2. Rede de seguranca generica: qualquer arquivo com o literal
     "memory" combinado a construcao de path (Path(), os.path.*,
     .parent, ou uso de uma variavel que foi atribuida via Path()/
     os.path.join/dirname em algum lugar do arquivo) E que NAO
     importa de iaglobal._paths -- pega variantes desconhecidas
     (BASE / "memory", etc.) ao custo de mensagens menos especificas.

Junta linhas com parenteses/colchetes nao fechados antes de aplicar
os padroes, entao chamadas multi-linha nao escapam mais.

Uso:
    python audit_path_sovereignty.py [raiz_do_pacote]
"""

import re
import sys
from pathlib import Path

SELF_PATH = Path(__file__).resolve()
CANONICAL_SOURCE = "_paths.py"
IGNORED_DIR_MARKERS = ("/.venv/", "/venv/", "/.git/", "/__pycache__/")

SEVERITY_ABSOLUTE = "CRITICO"
SEVERITY_KNOWN_PATTERN = "ALTO"
SEVERITY_GENERIC = "MEDIO"

KNOWN_PATTERNS = [
    (
        "Path(__file__).parent / memory",
        re.compile(r'Path\(__file__\)\.parent(\.parent)*\s*/\s*["\']memory["\']'),
    ),
    (
        "PACKAGE_DIR / memory",
        re.compile(r'PACKAGE_DIR(\.parent)?\s*/\s*["\']memory["\']'),
    ),
    (
        "Path(*ROOT) / iaglobal",
        re.compile(r'Path\([A-Za-z_]*ROOT\)\s*/\s*["\']iaglobal["\']'),
    ),
    (
        "os.path.join com memory/data",
        re.compile(r'os\.path\.join\([^)]*["\']memory["\']\s*,\s*["\']data["\']'),
    ),
    ("literal memory/data combinado", re.compile(r'["\']memory/data["\']')),
]

ABSOLUTE_HOME_PATTERN = re.compile(r'["\']\/home\/[a-zA-Z0-9_\-]+\/')
IMPORT_PATHS_PATTERN = re.compile(
    r"(from\s+iaglobal\._paths\s+import|import\s+iaglobal\._paths)"
)
MEMORY_LITERAL_PATTERN = re.compile(r'["\']memory["\']')
PATH_BUILDER_HINT_PATTERN = re.compile(r"Path\(|os\.path\.(join|dirname)|\.parent\b")
ASSIGNMENT_TO_PATHLIKE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=.*?(?:Path\(|os\.path\.(?:join|dirname))"
)


INLINE_TRIPLE_QUOTE = re.compile(r'""".*?"""|\'\'\'.*?\'\'\'')


def iter_code_lines(text: str):
    """Gera (lineno, trecho) pulando comentarios e blocos de docstring
    de linha tripla (inclusive docstrings de linha unica). Heuristica
    linha-a-linha, nao AST."""
    in_docstring = False
    delim = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if in_docstring:
            if delim in line:
                in_docstring = False
            continue

        # remove spans """....""" completos na mesma linha antes de
        # checar comentario/abertura de bloco multi-linha
        line = INLINE_TRIPLE_QUOTE.sub("", line)

        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        opened = False
        for d in ('"""', "'''"):
            if d in line and line.count(d) % 2 == 1:
                delim = d
                in_docstring = True
                opened = True
                break
        yield lineno, (line.split(delim, 1)[0] if opened else line)


def iter_logical_statements(code_lines):
    """Junta linhas com parenteses/colchetes nao fechados em uma unica
    'declaracao logica', preservando o numero da linha inicial."""
    buffer = []
    start = None
    depth = 0
    for lineno, line in code_lines:
        if depth == 0 and not buffer:
            start = lineno
        buffer.append(line)
        depth += line.count("(") + line.count("[") - line.count(")") - line.count("]")
        if depth <= 0:
            yield start, " ".join(buffer)
            buffer = []
            depth = 0
    if buffer:
        yield start, " ".join(buffer)


def find_path_like_vars(raw_text: str) -> set:
    """Variaveis cujo valor foi construido via Path()/os.path.join/dirname
    em qualquer linha do arquivo -- usado pra pegar uso indireto tipo
    'BASE / "memory"' onde BASE foi definido em outra linha."""
    names = set()
    for line in raw_text.splitlines():
        m = ASSIGNMENT_TO_PATHLIKE.search(line)
        if m:
            names.add(m.group(1))
    return names


def scan_file(path: Path):
    if path.resolve() == SELF_PATH:
        return []
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    has_paths_import = bool(IMPORT_PATHS_PATTERN.search(raw_text))
    code_lines = list(iter_code_lines(raw_text))
    statements = list(iter_logical_statements(code_lines))

    path_like_vars = find_path_like_vars(raw_text)
    var_usage_pattern = None
    if path_like_vars:
        alternation = "|".join(re.escape(v) for v in path_like_vars)
        var_usage_pattern = re.compile(rf"\b({alternation})\b\s*/")

    findings = []
    seen_lines = set()

    # Camada 1: padroes conhecidos
    for start, statement in statements:
        for label, pattern in KNOWN_PATTERNS:
            if pattern.search(statement):
                findings.append(
                    (
                        SEVERITY_KNOWN_PATTERN,
                        path,
                        start,
                        label,
                        statement.strip()[:120],
                    )
                )
                seen_lines.add(start)

    # Camada 2: rede generica -- so roda se o arquivo nao importa de _paths
    if not has_paths_import:
        for start, statement in statements:
            if start in seen_lines:
                continue
            has_memory_literal = MEMORY_LITERAL_PATTERN.search(statement)
            has_builder_hint = PATH_BUILDER_HINT_PATTERN.search(statement)
            has_tracked_var = var_usage_pattern and var_usage_pattern.search(statement)
            if has_memory_literal and (has_builder_hint or has_tracked_var):
                findings.append(
                    (
                        SEVERITY_GENERIC,
                        path,
                        start,
                        "memory + path builder, sem import _paths",
                        statement.strip()[:120],
                    )
                )
                seen_lines.add(start)

    # Path absoluto de home -- sempre critico, independente de import
    for lineno, line in code_lines:
        if ABSOLUTE_HOME_PATTERN.search(line):
            findings.append(
                (
                    SEVERITY_ABSOLUTE,
                    path,
                    lineno,
                    "path absoluto hardcoded",
                    line.strip()[:120],
                )
            )

    return findings


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    all_findings = []

    for py_file in root.rglob("*.py"):
        if py_file.name == CANONICAL_SOURCE:
            continue
        if any(marker in str(py_file) for marker in IGNORED_DIR_MARKERS):
            continue
        all_findings.extend(scan_file(py_file))

    if not all_findings:
        print("Nenhuma violacao de soberania de path encontrada.")
        return 0

    order = {SEVERITY_ABSOLUTE: 0, SEVERITY_KNOWN_PATTERN: 1, SEVERITY_GENERIC: 2}
    all_findings.sort(key=lambda f: (order[f[0]], str(f[1]), f[2]))

    current_severity = None
    for severity, path, lineno, label, snippet in all_findings:
        if severity != current_severity:
            print(f"\n=== {severity} ===")
            current_severity = severity
        print(f"  {path}:{lineno}: [{label}] {snippet}")

    affected_files = len({f[1] for f in all_findings})
    print(f"\nTotal: {len(all_findings)} ocorrencia(s) em {affected_files} arquivo(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
