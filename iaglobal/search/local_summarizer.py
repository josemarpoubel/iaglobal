# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
LocalSummarizer — Compressão algorítmica de outputs antes do Crítico.

Tolerante a múltiplas linguagens (Python, JS/TS, Go, Rust, Java, SQL, HTML,
CSS, YAML), indentação não-padrão e formatos híbridos.

Pipeline:
  1. Extrai blocos de código entre ```, independente da linguagem
  2. Extrai assinaturas via regex multi-linguagem (tolerante a indentação)
  3. Remove instruções de prompt e markdown boilerplate
  4. Remove linhas duplicadas e ruído
  5. Reconstrói: [Assinaturas] + [Código] + [Resumo]
"""

import re
from typing import List, Tuple


class LocalSummarizer:
    # Padrões de boilerplate multi-idioma
    _BOILERPLATE_PATTERNS = [
        r"Você é um especialista.*?(?=\n)",
        r"You are a.*?(?=\n)",
        r"Retorne APENAS.*?(?=\n)",
        r"Return ONLY.*?(?=\n)",
        r"NÃO inclua.*?(?=\n)",
        r"DO NOT include.*?(?=\n)",
        r"TIPO DE PROBLEMA.*?(?=\n)",
        r"INSTRUÇÃO.*?(?=\n)",
        r"INSTRUCTION.*?(?=\n)",
        r"TAREFA.*?(?=\n)",
        r"SAÍDA ESPERADA.*?(?=\n)",
        r"={3,}.*?={3,}",
        r"---{3,}",
        r"^#+ .*",  # Headers markdown
        r"\[//\]:.*",  # Comentários markdown
        r"<!--.*?-->",  # Comentários HTML
        r"```\w*",  # Abertura de code block (remove tag linguagem)
    ]

    # Prefixos de ruído de prompt (multi-idioma)
    _NOISE_PREFIXES = [
        "você é",
        "você deve",
        "você precisa",
        "seu papel",
        "sua tarefa",
        "retorne apenas",
        "não inclua",
        "não explique",
        "responda apenas",
        "atuando como",
        "como um especialista",
        "considerando que",
        "formato de saída",
        "saída esperada",
        "exemplo de saída",
        "use o contexto",
        "com base nas informações",
        "analise o",
        "you are",
        "you must",
        "you need to",
        "your role",
        "your task",
        "return only",
        "do not include",
        "do not explain",
        "acting as",
        "as an expert",
        "considering that",
        "output format",
        "expected output",
        "example output",
        "use the context",
        "based on the information",
    ]

    # Assinaturas multi-linguagem — cada padrão captura {lang, tipo, nome}
    _SIG_PATTERNS = [
        # Python
        (
            r"(?:async\s+)?def\s+(\w+)\s*\(.*?\)\s*(?:->\s*\w+(?:\[.*?\])?)?\s*:",
            "python",
            "def",
        ),
        (r"class\s+(\w+)\s*\(?.*?\)?\s*:", "python", "class"),
        (r"@\w+(?:\.\w+)?\(.*?\)", "python", "decorator"),
        # JavaScript / TypeScript
        (r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)", "js", "function"),
        (
            r"(?:export\s+)?(?:async\s+)?\(?\s*(?:\w+\s*:\s*\w+\s*,?\s*)*\s*\)?\s*=>",
            "js",
            "arrow",
        ),
        (
            r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+\w+(?:,\s*\w+)*)?",
            "js",
            "class",
        ),
        (
            r"(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+\w+(?:,\s*\w+)*)?",
            "ts",
            "interface",
        ),
        (r"(?:export\s+)?type\s+(\w+)\s*=", "ts", "type"),
        (r"const\s+(\w+)\s*(?::\s*\w+(?:<.*?>)?)?\s*=", "js", "const"),
        (r"(?:let|var)\s+(\w+)\s*(?::\s*\w+(?:<.*?>)?)?\s*=", "js", "var"),
        # Go
        (r"func\s+(?:\(.*?\)\s+)?(\w+)\s*\([^)]*\)\s*(?:\(?[^)]*\)?)?", "go", "func"),
        (r"type\s+(\w+)\s+struct", "go", "struct"),
        (r"type\s+(\w+)\s+interface", "go", "interface"),
        (r"func\s+\(.*?\)\s+(\w+)\s*\([^)]*\)\s*(?:\(?[^)]*\)?)?", "go", "method"),
        # Rust
        (
            r"fn\s+(\w+)\s*<.*?>\s*\([^)]*\)\s*(?:->\s*(?:&?\w+(?:<.*?>)?)\s*)?",
            "rust",
            "fn",
        ),
        (r"struct\s+(\w+)(?:<.*?>)?", "rust", "struct"),
        (r"enum\s+(\w+)(?:<.*?>)?", "rust", "enum"),
        (r"impl\s+(\w+(?:<.*?>)?)", "rust", "impl"),
        (r"trait\s+(\w+)(?:<.*?>)?", "rust", "trait"),
        # Java
        (
            r"(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:\w+(?:<.*?>)?\s+)?(\w+)\s*\([^)]*\)\s*(?:\{|throws)",
            "java",
            "method",
        ),
        (
            r"(?:public|private|protected)\s+(?:static\s+)?(?:abstract\s+)?class\s+(\w+)",
            "java",
            "class",
        ),
        (r"(?:public|private|protected)\s+interface\s+(\w+)", "java", "interface"),
        # SQL
        (
            r"(?:CREATE|ALTER|DROP)\s+(?:TABLE|VIEW|INDEX|PROCEDURE|FUNCTION|TRIGGER)\s+(\w+)",
            "sql",
            "ddl",
        ),
        (r"SELECT\s+.*?\s+FROM\s+(\w+)", "sql", "query"),
        # C / C++
        (
            r"(?:int|void|char|float|double|long|short|unsigned|size_t|bool|FILE|struct\s+\w+|\w+_t)\s+(\w+)\s*\([^)]*\)\s*(?:\{|;)",
            "c",
            "function",
        ),
        # Ruby
        (r"def\s+(?:self\.)?(\w+)\s*\(?[^)]*\)?", "ruby", "def"),
        (r"class\s+(\w+)(?:\s*<.*?)?", "ruby", "class"),
        # Docker / YAML
        (r"FROM\s+(\w+(?:/\w+)?(?::\w+)?)", "docker", "from"),
        (r"^\w+:\s*$", "yaml", "key"),
    ]

    # Linguagens de bloco de código para relatório
    _CODE_LANG_ALIAS = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "go": "golang",
        "rs": "rust",
        "rb": "ruby",
        "html": "html",
        "css": "css",
        "sql": "sql",
        "yaml": "yaml",
        "yml": "yaml",
        "json": "json",
        "xml": "xml",
        "bash": "bash",
        "sh": "bash",
        "dockerfile": "docker",
        "makefile": "make",
    }

    @classmethod
    def compress(cls, task: str, output: str) -> Tuple[str, str]:
        """Comprime task e output preservando apenas o sinal relevante."""
        task = cls._compress_text(task, max_chars=600)
        output = cls._compress_output(output, max_chars=3000)
        return task, output

    @classmethod
    def _compress_text(cls, text: str, max_chars: int = 600) -> str:
        """Remove boilerplate e comprime texto genérico."""
        text = text.strip()
        for pat in cls._BOILERPLATE_PATTERNS:
            text = re.sub(pat, "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = " ".join(text.split())
        return text[:max_chars]

    @classmethod
    def _compress_output(cls, output: str, max_chars: int = 3000) -> str:
        """Comprime output preservando código e assinaturas — descarta verbosidade."""
        if not output.strip():
            return ""

        # 1. Extrai blocos de código (qualquer linguagem)
        code_blocks = cls._extract_code_blocks(output)
        clean_code = "\n".join(cb.strip() for cb in code_blocks if cb.strip())

        # 2. Extrai assinaturas multi-linguagem
        signatures = cls._extract_signatures(output)

        # 3. Remove boilerplate do texto residual
        text_residual = cls._compress_text(output, max_chars=1200)

        # 4. Remove linhas de ruído de prompt
        text_residual = cls._remove_prompt_noise(text_residual)

        # 5. Remove linhas duplicadas consecutivas e quase-duplicadas
        text_residual = cls._dedup_lines(text_residual)

        # 6. Monta resultado compacto com seções
        parts = []
        if signatures:
            parts.append(f"[Assinaturas]\n{signatures}")
        if clean_code:
            code_truncated = clean_code[:max_chars]
            # Identifica linguagem do primeiro bloco de código
            lang_hint = cls._detect_language(clean_code)
            if lang_hint:
                parts.append(f"[Codigo/{lang_hint}]\n{code_truncated}")
            else:
                parts.append(f"[Codigo]\n{code_truncated}")
        if text_residual and len(text_residual) > 30:
            text_truncated = text_residual[:600]
            parts.append(f"[Resumo]\n{text_truncated}")

        compressed = "\n\n".join(parts)
        return compressed[:max_chars]

    # ─── extração de blocos de código (tolerante) ──────────────

    @classmethod
    def _extract_code_blocks(cls, text: str) -> List[str]:
        """Extrai blocos de código entre ```, ignorando abertura/fechamento mal formados."""
        blocks = []

        # Fenced blocks: ```lang ... ```
        fenced = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        blocks.extend(fenced)

        # Indented blocks (4+ spaces) — common in Markdown
        indented = re.findall(r"(?:^|\n)(?: {4,}|\t+)(.*?)(?=\n\S|\Z)", text, re.DOTALL)
        if indented:
            joined = "\n".join(
                re.sub(r"^ {4}", "", line) for line in indented if line.strip()
            )
            if joined.strip():
                blocks.append(joined)

        return blocks

    @classmethod
    def _detect_language(cls, code: str) -> str:
        """Detecta a linguagem do código baseado em heurísticas."""
        checks = [
            (r"\bdef\s+\w+\s*\(", "python"),
            (r"\bimport\s+\w+", "python"),
            (r"\bfrom\s+\w+\s+import", "python"),
            (r"\basync\s+def\s+", "python"),
            (r"\bclass\s+\w+\s*:", "python"),
            (r"@\w+\.\w+\(.*?\)", "python"),
            (r"\bfunction\s+\w+", "javascript"),
            (r"\bconst\s+\w+\s*=\s*(?:async\s*)?\(", "javascript"),
            (r"\blet\s+\w+", "javascript"),
            (r"\bexport\s+(?:default\s+)?(?:function|class|const)", "javascript"),
            (r"=>\s*{", "javascript"),
            (r":\s*string|:\s*number|:\s*boolean|:\s*any|:\s*void", "typescript"),
            (r"\binterface\s+\w+", "typescript"),
            (r"\btype\s+\w+\s*=", "typescript"),
            (r"\bfunc\s+\w+", "go"),
            (r"\btype\s+\w+\s+struct", "go"),
            (r"\bfn\s+\w+", "rust"),
            (r"\bimpl\s+\w+", "rust"),
            (r"\b(?:public|private|protected)\s+class\s+\w+", "java"),
            (r"\bvoid\s+\w+\(", "java"),
            (r"CREATE\s+TABLE", "sql"),
            (r"SELECT\s+.*?\s+FROM", "sql"),
            (r"<!DOCTYPE", "html"),
            (r"<html", "html"),
            (r"<div|<span|<a\s+|<input|<button", "html"),
            (r"FROM\s+\w+(?:/\w+)?(?::\w+)?", "dockerfile"),
            (r"RUN\s+", "dockerfile"),
        ]
        for pat, lang in checks:
            if re.search(pat, code, re.IGNORECASE):
                return lang
        return ""

    # ─── extração de assinaturas (multi-linguagem, tolerante) ──

    @classmethod
    def _extract_signatures(cls, text: str) -> str:
        """Extrai assinaturas de função/classe/import de múltiplas linguagens.

        Tolerante a indentação não-padrão: usa re.search linha a linha
        em vez de re.match que exigiria início da linha.
        """
        seen: set = set()
        sigs: List[str] = []

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "--", "/*", "*")):
                continue
            if stripped in seen:
                continue
            for pat, _lang, _stype in cls._SIG_PATTERNS:
                m = re.search(pat, stripped)
                if m:
                    # Pega a linha toda como assinatura (para contexto)
                    # mas trunca em 120 chars para não poluir
                    sig_line = stripped[:120]
                    if sig_line not in seen:
                        seen.add(sig_line)
                        sigs.append(sig_line)
                    break

        return "\n".join(sigs[:20])

    # ─── limpeza de ruído ─────────────────────────────────────

    @staticmethod
    def _remove_prompt_noise(text: str) -> str:
        """Remove linhas que parecem instruções de prompt."""
        lines = text.split("\n")
        clean = []
        for line in lines:
            stripped = line.strip().lower()
            if any(stripped.startswith(p) for p in LocalSummarizer._NOISE_PREFIXES):
                continue
            if len(stripped) < 5:
                continue
            clean.append(line)
        return "\n".join(clean)

    @staticmethod
    def _dedup_lines(text: str) -> str:
        """Remove linhas consecutivas duplicadas e quase-duplicadas."""
        lines = text.split("\n")
        deduped = []
        for i, line in enumerate(lines):
            s = line.strip()
            if i > 0:
                prev = lines[i - 1].strip()
                # Exato duplicado
                if s == prev:
                    continue
                # Quase duplicado (diff < 3 chars de Levenshtein simplificado)
                if s and prev and abs(len(s) - len(prev)) < 3 and s[:10] == prev[:10]:
                    continue
            deduped.append(line)
        return "\n".join(deduped)
