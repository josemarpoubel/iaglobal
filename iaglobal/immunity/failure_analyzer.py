# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal/immunity/failure_analyzer.py

FailureAnalyzer — Sistema de Vigilância Imunológica para Falhas de Código.

Modelo biológico: macrófago tecidual — patrulha o microambiente (output do
code_executor), reconhece padrões de dano (erros), apresenta antígenos
(diagnósticos) aos linfócitos T (Crítico), e registra memória (vacinas)
no ledger imunológico (VaccineLedger).

Ciclo completo:
  1. PATRULHA: code_executor retorna output bruto
  2. RECONHECIMENTO: parse_error() → DiagnosticoFalha estruturado
  3. FINGERPRINT: fingerprint_error() → hash SHA256 sanitizado
  4. MEMÓRIA: check_vaccine() → consulta VaccineLedger
  5. APRESENTAÇÃO: generate_correction_plan() → plano para o Crítico
  6. IMUNIZAÇÃO: register_vaccine() → persiste no ledger
"""

import hashlib
import re
import traceback
from typing import Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.immunity.failure_analyzer")

LINEAGE_MARKER = "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"


# ── Padrões de erro conhecidos ──────────────────────────────────────
# Ordem importa: padrões mais específicos primeiro

_ERROR_PATTERNS = [
    (r"SyntaxError", "SyntaxError"),
    (r"IndentationError", "IndentationError"),
    (r"Timeout", "TimeoutError"),
    (r"TimeoutExpired", "TimeoutError"),
    (r"ModuleNotFoundError|ImportError.*No module named", "ImportError"),
    (r"ImportError", "ImportError"),
    (r"NameError", "NameError"),
    (r"TypeError", "TypeError"),
    (r"ValueError", "ValueError"),
    (r"KeyError", "KeyError"),
    (r"IndexError", "IndexError"),
    (r"AttributeError", "AttributeError"),
    (r"ZeroDivisionError", "ZeroDivisionError"),
    (r"AssertionError", "AssertionError"),
    (r"FileNotFoundError", "FileNotFoundError"),
    (r"PermissionError", "PermissionError"),
    (r"ConnectionError|ConnectionRefusedError|ConnectionResetError", "ConnectionError"),
    (r"OSError", "OSError"),
    (r"RuntimeError", "RuntimeError"),
    (r"StopIteration", "StopIteration"),
    (r"OverflowError", "OverflowError"),
    (r"RecursionError", "RecursionError"),
    (r"KeyboardInterrupt", "KeyboardInterrupt"),
    (r"MemoryError", "MemoryError"),
    (r"SystemExit", "SystemExit"),
    (r"EOFError", "EOFError"),
    (r"FloatingPointError", "FloatingPointError"),
    (r"Exception", "RuntimeError"),
]

_LINE_PATTERN = re.compile(r'line\s+(\d+)', re.IGNORECASE)
_FILE_PATTERN = re.compile(r'File\s+"([^"]+)"', re.IGNORECASE)
_ERROR_LINE_PATTERN = re.compile(
    r'(?:Traceback.*\n)?.*?(?:Error|Exception|Timeout|Warning):\s*(.*)',
    re.DOTALL,
)
_TRACEBACK_CLEAN_PATTERN = re.compile(r'/home/[^/]+/[^\s:]+')


def _sanitize_paths(text: str) -> str:
    """Remove caminhos absolutos do traceback para fingerprint determinístico."""
    return _TRACEBACK_CLEAN_PATTERN.sub("/sanitized/path", text)


def _extract_error_type(output: str) -> str:
    """Extrai o tipo de erro do output."""
    for pattern, error_type in _ERROR_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            return error_type
    if not output or not output.strip():
        return "EmptyOutput"
    return "Unknown"


def _extract_error_message(output: str) -> str:
    """Extrai a mensagem principal do erro."""
    lines = output.strip().splitlines()
    significant = [l for l in lines if l.strip() and not l.startswith("[") and "exit code" not in l and "stderr" not in l]
    if not significant:
        return output[:200]
    for line in reversed(significant):
        if "Error:" in line or "Exception:" in line:
            idx = line.index("Error:") if "Error:" in line else line.index("Exception:")
            return line[idx:].strip()
    for line in reversed(significant):
        if "Error" in line or "Exception" in line or "Timeout" in line:
            return line.strip()
    return significant[-1][:200]


def _extract_line(output: str) -> Optional[int]:
    """Extrai o número da linha do erro."""
    match = _LINE_PATTERN.search(output)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def _extract_file(output: str) -> Optional[str]:
    """Extrai o nome do arquivo do traceback."""
    match = _FILE_PATTERN.search(output)
    return match.group(1) if match else None


def parse_error(
    output: str,
    original_code: str = "",
) -> "DiagnosticoFalha":
    """
    Converte output bruto do code_executor em DiagnosticoFalha estruturado.

    Args:
        output: stdout/stderr retornado pelo code_executor
        original_code: código que foi executado (opcional, para referência)

    Returns:
        DiagnosticoFalha com tipo, mensagem, linha, fingerprint
    """
    from iaglobal.interface.diagnostico import DiagnosticoFalha

    tipo = _extract_error_type(output)
    msg = _extract_error_message(output)
    linha = _extract_line(output)
    arquivo = _extract_file(output)
    fp = fingerprint_error(output)

    return DiagnosticoFalha(
        tipo_erro=tipo,
        mensagem=msg,
        linha=linha,
        arquivo=arquivo,
        fingerprint=fp,
        codigo_original=original_code,
        output_bruto=output,
    )


def fingerprint_error(traceback_str: str) -> str:
    """
    Gera fingerprint SHA256 determinístico do traceback sanitizado.

    A sanitização remove:
    - Caminhos absolutos (/home/user/project/... → /sanitized/path)
    - Números de linha específicos (line 42 → line N)
    - Variações de timestamp

    Isso garante que o mesmo erro em ambientes diferentes gere o mesmo
    fingerprint → vacina universal.
    """
    cleaned = _sanitize_paths(traceback_str)
    cleaned = re.sub(r'line \d+', 'line N', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', cleaned)
    return hashlib.sha256(cleaned.encode()).hexdigest()


async def check_vaccine(
    diagnostico: "DiagnosticoFalha",
    lineage_marker: str = "",
) -> Optional[str]:
    """
    Consulta o VaccineLedger se o fingerprint já foi visto.

    Args:
        diagnostico: diagnóstico da falha
        lineage_marker: linhagem do agente (para consulta no ledger)

    Returns:
        Código de correção se houver vacina, None se for novo padrão
    """
    if not diagnostico.fingerprint:
        return None
    try:
        from iaglobal.immunity.vaccine_ledger import vaccine_ledger

        vacinas = await vaccine_ledger.vacinas(lineage_marker)
        fp = diagnostico.fingerprint
        for v in vacinas:
            if fp in v:
                logger.info(
                    "[FAILURE_ANALYZER] Vacina encontrada para fingerprint %s...",
                    fp[:16],
                )
                parts = v.split("::", 1)
                return parts[1] if len(parts) > 1 else None
    except Exception as e:
        logger.debug("[FAILURE_ANALYZER] check_vaccine: %s", e)
    return None


async def register_vaccine(
    diagnostico: "DiagnosticoFalha",
    correction: str,
    evo=None,
    lineage_marker: str = "",
) -> None:
    """
    Registra um novo padrão de falha como vacina no VaccineLedger.

    O padrão é armazenado como:
        <fingerprint>::<correction_resumida>

    Args:
        diagnostico: diagnóstico da falha
        correction: código de correção aplicado
        evo: instância do EvoAgent (opcional, usado para lineage_marker)
        lineage_marker: fallback se evo não for fornecido
    """
    if not diagnostico.fingerprint or not correction:
        return

    try:
        from iaglobal.immunity.vaccine_ledger import vaccine_ledger

        marker = getattr(evo, "lineage_marker", None) or lineage_marker
        if not marker:
            logger.debug("[FAILURE_ANALYZER] Sem lineage_marker — vacina não registrada")
            return

        pattern = f"{diagnostico.fingerprint}::type={diagnostico.tipo_erro}"
        context = {
            "tipo_erro": diagnostico.tipo_erro,
            "mensagem": diagnostico.mensagem[:120],
            "correction_preview": correction[:200],
        }
        await vaccine_ledger.registrar_falha(
            type("_EvoProxy", (), {"lineage_marker": marker, "name": "failure_analyzer"})(),
            pattern,
            context,
        )
        logger.info(
            "[FAILURE_ANALYZER] Vacina registrada: %s... (%s, %d chars)",
            diagnostico.fingerprint[:16],
            diagnostico.tipo_erro,
            len(correction),
        )
    except Exception as e:
        logger.debug("[FAILURE_ANALYZER] register_vaccine: %s", e)


def generate_correction_plan(
    diagnostico: "DiagnosticoFalha",
    original_code: str = "",
) -> str:
    """
    Gera um plano de correção determinístico baseado no tipo de erro.

    Para erros comuns (SyntaxError, ImportError, NameError), gera sugestão
    sem custo de LLM. Para erros complexos, retorna None e delega ao
    Crítico via arbitrar_geracao().

    Args:
        diagnostico: diagnóstico da falha
        original_code: código original que falhou

    Returns:
        Código corrigido (se correção determinística possível) ou string vazia
    """
    code = original_code or diagnostico.codigo_original
    if not code:
        return ""

    lines = code.splitlines()
    error_type = diagnostico.tipo_erro
    error_line = diagnostico.linha

    if error_type == "SyntaxError" and error_line:
        return _fix_syntax_error(code, error_line)
    if error_type == "IndentationError" and error_line:
        return _fix_indentation(code)
    if error_type == "ImportError":
        return _fix_import_error(code, diagnostico.mensagem)
    if error_type == "NameError":
        return _fix_name_error(code, diagnostico.mensagem)
    if error_type == "EmptyOutput":
        return _fix_empty_output(code)
    if error_type == "TimeoutError":
        return _fix_timeout(code)

    return ""


def _fix_syntax_error(code: str, error_line: int) -> str:
    """Tenta corrigir SyntaxError: parênteses, colchetes, aspas."""
    lines = code.splitlines()
    if error_line and 0 < error_line <= len(lines):
        line = lines[error_line - 1]
        stripped = line.strip()
        if stripped.endswith(("=", "+", "-", "*", "/", "\\", ",")):
            lines[error_line - 1] = line.rstrip().rstrip("=+-*/\\,")
        if stripped.count("(") > stripped.count(")"):
            lines[error_line - 1] = line + ")"
        if stripped.count("[") > stripped.count("]"):
            lines[error_line - 1] = line + "]"
        if stripped.count("{") > stripped.count("}"):
            lines[error_line - 1] = line + "}"
        if stripped.count('"') % 2 != 0:
            lines[error_line - 1] = line + '"'
        if stripped.count("'") % 2 != 0:
            lines[error_line - 1] = line + "'"
    return "\n".join(lines)


def _fix_indentation(code: str) -> str:
    """Normaliza indentação para 4 espaços."""
    lines = code.splitlines()
    fixed = []
    for line in lines:
        if line.strip():
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]
            fixed_spaces = leading.replace("\t", "    ")
            fixed.append(fixed_spaces + stripped)
        else:
            fixed.append("")
    return "\n".join(fixed)


def _fix_import_error(code: str, message: str) -> str:
    """Envolve import problemático em try/except."""
    msg_lower = message.lower()
    for pattern in [r"'(.*?)'", r'"(.*?)"']:
        match = re.search(pattern, msg_lower)
        if match:
            module = match.group(1)
            break
    else:
        module = "unknown_module"

    import_line = None
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if f"import {module}" in line or f"from {module}" in line:
            import_line = i
            break

    if import_line is not None:
        indent = " " * (len(lines[import_line]) - len(lines[import_line].lstrip()))
        try_block = [
            f"{indent}try:",
            f"{indent}    {lines[import_line].strip()}",
            f"{indent}except ImportError:",
            f'{indent}    pass  # {module} not available — graceful degradation',
        ]
        lines[import_line:import_line + 1] = try_block
    return "\n".join(lines)


def _fix_name_error(code: str, message: str) -> str:
    """Declara variável não definida como None antes do uso."""
    msg_lower = message.lower()
    match = re.search(r"name\s+'(\w+)'", msg_lower)
    if match:
        var_name = match.group(1)
        lines = code.splitlines()
        for i, line in enumerate(lines):
            if var_name in line and "=" not in line.split(var_name)[0]:
                indent = " " * (len(line) - len(line.lstrip()))
                lines.insert(i, f"{indent}{var_name} = None  # auto-declared by FailureAnalyzer")
                break
        return "\n".join(lines)
    return code


def _fix_empty_output(code: str) -> str:
    """Adiciona print() se o código não produz saída."""
    lines = code.splitlines()
    if not lines:
        return 'print("No output produced")'
    last = lines[-1].strip()
    if last and not last.startswith(("print", "return", "assert", "#", "def ", "class ", "import ", "from ")):
        if not any(kw in last for kw in ("=", "for ", "while ", "if ", "try:", "except", "with ")):
            indent = " " * (len(lines[-1]) - len(lines[-1].lstrip()))
            lines.append(f"{indent}print({last})")
    return "\n".join(lines)


def _fix_timeout(code: str) -> str:
    """Adiciona otimizações para prevenir timeout (reduz loops grandes)."""
    lines = code.splitlines()
    fixed = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("for ") or stripped.startswith("while "):
            indent = " " * (len(line) - len(stripped))
            fixed.append(f"{indent}# OPTIMIZED: {stripped}")
        else:
            fixed.append(line)
    return "\n".join(fixed) if fixed != lines else code
