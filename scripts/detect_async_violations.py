#!/usr/bin/env python3
"""
🧬 Async Violation Detector - Metabolic Scanner
Detecta violações REAIS de async/await no código iaglobal.

Baseado nas Leis Universais:
- Lei da Obediência: async-first obrigatório (I/O via asyncio.to_thread)
- Lei da Ordem: metadata e contexto preservados na ordem correta
- Lei da Caridade: erros enriquecidos com contexto antes de repassar
- Axioma da Homeostase: detecção antecipatória de desequilíbrios
"""
import ast
import pathlib
import re
from typing import List, Dict, Set

IAGLOBAL_ROOT = pathlib.Path(__file__).parent.parent

# Métodos async-safe conhecidos
ASYNC_SAFE_CALLS = {
    "asyncio.to_thread", "asyncio.run", "asyncio.create_task",
    "asyncio.gather", "asyncio.wait_for", "asyncio.sleep",
    "run_async_safe",
}

# I/O REALMENTE BLOQUEANTE (disk, network, db, subprocess)
BLOCKING_IO_PATTERNS = {
    # File I/O real
    ".write_text(", ".read_text(", ".write_bytes(", ".read_bytes(",
    "open(", ".close()",
    # Path operations que tocam disco
    ".mkdir(", ".unlink(", ".stat(", ".glob(", ".rglob(",
    "iterdir(", "readlink(", "exists(",
    # Serialization I/O
    "json.dump(", "json.load(",
    "cbor2.dump(", "cbor2.load(", "pickle.dump(", "pickle.load(",
    # Network/HTTP
    "requests.get(", "requests.post(", "requests.put(", "requests.delete(",
    "requests.request(", "httpx.get(", "httpx.post(", "httpx.put(",
    "httpx.delete(", "httpx.request(",
    # Database
    "sqlite3.connect(", "sqlite3.Cursor(", ".execute(", ".fetch",
    ".commit(", ".rollback(",
    # Subprocess/OS
    "subprocess.run(", "subprocess.Popen(", "os.system(", "os.popen(",
    # Time (blocking)
    "time.sleep(",
}

# Operações CPU-only (false positives para filtrar)
CPU_ONLY_PATTERNS = {
    # String manipulation
    ".replace(", ".strip(", ".split(", ".join(", ".lower(", ".upper(",
    ".title(", ".capitalize(", ".format(", "f\"", "f'",
    # Regex
    "re.sub(", "re.search(", "re.match(", "re.findall(", "re.compile(",
    # List/dict ops
    ".append(", ".extend(", ".pop(", ".remove(", ".sort(", ".reverse(",
    "len(", "sum(", "max(", "min(", "sorted(", "enumerate(", "zip(",
    # Path manipulation (sem tocar disco)
    "Path(", "pathlib", ".name", ".stem", ".suffix", ".parent",
    ".parts", ".as_posix(", "__str__", "__repr__",
    # Type/attribute access
    "isinstance(", "hasattr(", "getattr(", "setattr(",
    # Model cleaning (string ops)
    "model.replace(", "model_clean", "clean_model",
}

# Padrões de bugs críticos conhecidos (do diagnóstico)
CRITICAL_BUGS = {
    "asyncio.get_event_loop().time()": "BUG #2 - deprecated, use time.time() or get_running_loop()",
    "asyncio.run(": "BUG #4 - falha dentro de loop ativo, use nest_asyncio ou loop.run_until_complete",
    "registrar_erro(": "BUG #1 - chamado sem await, erros NÃO capturados",
    "sussurrar_intuicao(": "BUG #3 - chamado sem await, prompt recebe coroutine",
    "obter_insight_subconsciente(": "BUG #3 - chamado sem await, prompt recebe coroutine",
}

# Entry points legítimos para asyncio.run()
LEGIT_ENTRY_POINTS = {
    "__main__.py", "cli.py", "main.py", "run_cli.py",
    "evolution_lab.py", "node_timing.py", "genesis_purifier.py",
    "detect_async_violations.py", "gravar_instintos.py",
    "hf_video_provider.py", "helpers.py", "demo.py",
    "subconsciousapi.py",  # Wrapper sync legítimo (_sync_wrap)
}


def is_legitimate_entry_point(filepath: pathlib.Path, func_name: str) -> bool:
    """Verifica se asyncio.run() é legítimo neste contexto."""
    filename = filepath.name
    if filename in LEGIT_ENTRY_POINTS:
        return True
    if filename.startswith("test_") or filename.startswith("demo"):
        return True
    if func_name in ("main", "run_cli", "run", "execute", "demo"):
        return True
    return False


def check_file(filepath: pathlib.Path) -> List[Dict]:
    """Retorna lista de violações REAIS encontradas no arquivo."""
    violations = []
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    lines = source.split('\n')
    in_async = False
    async_func_name = ""
    in_class = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comments and docstrings
        if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        # Detect async function entry
        if 'async def ' in stripped:
            in_async = True
            match = re.search(r'async def\s+(\w+)', stripped)
            if match:
                async_func_name = match.group(1)
        elif stripped.startswith('def ') and in_async and not stripped.startswith('async def'):
            in_async = False
            async_func_name = ""
        elif stripped.startswith('class '):
            in_class = True
        elif in_class and stripped and not stripped.startswith(' ') and not stripped.startswith('\t'):
            in_class = False

        # Check CRITICAL known bugs
        for pattern, description in CRITICAL_BUGS.items():
            if pattern in line and not stripped.startswith('#'):
                # Ignore async-safe context (asyncio.run em entry point legítimo)
                if pattern == "asyncio.run(" and is_legitimate_entry_point(filepath, async_func_name):
                    continue
                # Ignore se a linha tem await antes do padrão (chamada async legítima)
                if "await " in stripped and not pattern.startswith("asyncio."):
                    continue
                # Ignore definições de função/método (não são chamadas)
                if re.search(r'\bdef\s+\w+\s*\(', stripped):
                    continue
                # Ignore entradas de dicionário de configuração (strings descritivas)
                if re.search(r'["\']\s*:\s*["\']BUG|CRITICAL', stripped):
                    continue
                violations.append({
                    "file": str(filepath),
                    "line": i,
                    "code": stripped[:120],
                    "async_func": async_func_name if in_async else ("class" if in_class else "module"),
                    "type": "CRITICAL_BUG",
                    "law": description,
                })

        # Check blocking I/O inside async functions
        if in_async:
            for pattern in BLOCKING_IO_PATTERNS:
                if pattern in line:
                    # Check if properly wrapped
                    if 'asyncio.to_thread' in line:
                        continue
                    if any(safe in line for safe in ASYNC_SAFE_CALLS):
                        continue
                    # Se a linha tem 'await' antes do padrão, é chamada async legítima
                    if 'await ' in stripped:
                        continue
                    # Filter CPU-only false positives
                    if any(cpu in line for cpu in CPU_ONLY_PATTERNS):
                        continue
                    # Filter string ops that look like I/O but aren't
                    if pattern in (".write_text(", ".read_text(", ".write_bytes(", ".read_bytes("):
                        if ".replace(" in line or ".strip(" in line or "re.sub(" in line:
                            continue
                    violations.append({
                        "file": str(filepath),
                        "line": i,
                        "code": stripped[:120],
                        "async_func": async_func_name,
                        "type": "BLOCKING_IO_IN_ASYNC",
                        "law": "Lei da Obediência - I/O bloqueante deve usar asyncio.to_thread",
                    })

        # Check missing await on known async methods
        if in_async:
            await_patterns = [
                r'\.registrar_erro\(',
                r'\.sussurrar_intuicao\(',
                r'\.obter_insight_subconsciente\(',
                r'\.escrever_curto_prazo\(',
                r'\.escrever_longo_prazo\(',
                r'\.escrever_instinto\(',
                r'\.ler_nota\(',
                r'\.listar_notas\(',
                r'\.atualizar_mapa_conexoes\(',
                r'\.exportar_nota_agente\(',
            ]
            for pat in await_patterns:
                if re.search(pat, line) and 'await ' not in line and 'asyncio.create_task' not in line:
                    violations.append({
                        "file": str(filepath),
                        "line": i,
                        "code": stripped[:120],
                        "async_func": async_func_name,
                        "type": "MISSING_AWAIT",
                        "law": "Lei da Obediência - chamadas async devem ser awaited",
                    })

    return violations


def main():
    violations = []
    
    py_files = list(IAGLOBAL_ROOT.rglob("iaglobal/**/*.py"))
    py_files.extend(IAGLOBAL_ROOT.rglob("scripts/**/*.py"))
    
    for f in py_files:
        # Não escanear o detector a si mesmo para evitar falsos positivos cascata
        if f.name == "detect_async_violations.py":
            continue
        if '__pycache__' in str(f) or 'venv' in str(f) or '.pytest_cache' in str(f):
            continue
        v = check_file(f)
        if v:
            violations.extend(v)

    if violations:
        print(f"\n🔴 Found {len(violations)} REAL async violations:\n")
        
        by_type: Dict[str, List] = {}
        for v in violations:
            by_type.setdefault(v["type"], []).append(v)
        
        for vtype, vlist in by_type.items():
            print(f"  📋 {vtype} ({len(vlist)} ocorrências):")
            for v in sorted(vlist, key=lambda x: (x["file"], x["line"])):
                rel_path = pathlib.Path(v["file"]).relative_to(IAGLOBAL_ROOT)
                print(f"    {rel_path}:{v['line']} [{v['async_func']}]")
                print(f"      ⚖️  {v['law']}")
                print(f"      💻 {v['code']}")
                print()
    else:
        print("✅ No async violations detected - Lei da Obediência respeitada")

    return 1 if violations else 0


if __name__ == "__main__":
    exit(main())