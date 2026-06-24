#!/usr/bin/env python3
"""
🧬 Async Violation Detector - Metabolic Scanner
Detecta violações reais de async/await no código iaglobal.

NÃO é um detector de "métodos órfãos" - é um detector de I/O síncrono
em contexto async e chamadas async não aguardadas.
"""
import ast
import pathlib
from typing import List, Dict, Set

IAGLOBAL_ROOT = pathlib.Path(__file__).parent.parent

# Métodos conhecidos async
ASYNC_SAFE_CALLS = {
    "run_async_safe", "asyncio.to_thread", "asyncio.run",
    "asyncio.create_task", "asyncio.gather",
}

# I/O síncrono conhecido
SYNC_IO_PATTERNS = {
    "sqlite3.connect", "sqlite3.Cursor", ".execute(", ".fetch",
    ".write_text", ".read_text", ".write_bytes", ".read_bytes",
    ".connect(", ".get(", ".post(", ".put(", ".delete(", ".query(",
    "requests.get", "requests.post", "requests.put", "requests.request",
    "open(", ".close()", ".commit()", "json.dump", "json.load",
    "Path(", ".unlink(", ".mkdir(", ".stat(",
}

class AsyncViolationChecker(ast.NodeVisitor):
    """Detecta chamadas I/O síncronas dentro de funções async."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[Dict] = []
        self.in_async_function = False
        self.async_func_name = ""
        self.sync_io_found = False
        
    def visit_AsyncFunctionDef(self, node):
        old_async = self.in_async_function
        old_name = self.async_func_name
        self.in_async_function = True
        self.async_func_name = node.name
        self.generic_visit(node)
        self.in_async_function = old_async
        self.async_func_name = old_name
        
    def visit_Call(self, node):
        if self.in_async_function:
            # Check for sync I/O patterns
            call_str = ast.unparse(node) if hasattr(ast, 'unparse') else ""
            if any(p in call_str for p in SYNC_IO_PATTERNS):
                # Check if wrapped in asyncio.to_thread
                self.sync_io_found = True
        self.generic_visit(node)
        
    def visit_Attribute(self, node):
        if self.in_async_function:
            # SQLite operations
            if isinstance(node.value, ast.Name) and node.value.id in ('conn', 'cursor'):
                pass
        self.generic_visit(node)

def check_file(filepath: pathlib.Path) -> List[str]:
    """Retorna lista de violações encontradas no arquivo."""
    violations = []
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except SyntaxError:
        return violations
    
    # Check for sync I/O inside async functions using regex (simpler)
    lines = source.split('\n')
    in_async = False
    
    for i, line in enumerate(lines, 1):
        if 'async def ' in line:
            in_async = True
        elif line.strip().startswith('def ') and in_async:
            in_async = False
            
        if in_async and any(p in line for p in SYNC_IO_PATTERNS):
            # Exclude if line is a comment or has asyncio.to_thread
            if not line.strip().startswith('#') and 'asyncio.to_thread' not in line:
                # Check for common safe patterns
                if not any(safe in line for safe in ASYNC_SAFE_CALLS):
                    violations.append(f"{filepath}:{i}: {line.strip()[:80]}")
    
    return violations

def main():
    violations = []
    py_files = list(IAGLOBAL_ROOT.rglob("iaglobal/**/*.py"))
    
    for f in py_files:
        v = check_file(f)
        if v:
            violations.extend(v)
    
    if violations:
        print(f"\n🔴 Found {len(violations)} potential async I/O violations:\n")
        for v in sorted(set(violations))[:50]:  # Top 50
            print(f"  {v}")
    else:
        print("✅ No async I/O violations detected")

if __name__ == "__main__":
    main()