#!/usr/bin/env python3
"""
Script inteligente de correção de indentação.

Analisa o contexto (try, for, if, def, class) e adiciona a indentação correta.
"""

import subprocess
import re
from pathlib import Path
import sys

AGENTS_DIR = Path(__file__).parent.parent / "iaglobal" / "agents"

INDENT = ' ' * 8  # 8 espaços padrão do projeto

def get_compile_error(filepath: Path) -> tuple:
    """Executa py_compile e extrai informações do erro."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(filepath)],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        return None
    
    # Parse: "IndentationError: expected an indented block after 'try' statement on line X (file.py, line Y)"
    match = re.search(r"after '(\w+)' statement on line (\d+)", result.stderr)
    if match:
        context_keyword = match.group(1)
        line_num = int(match.group(2))
        return (line_num, f"expected indent after {context_keyword}", context_keyword)
    
    # Parse alternativo: "IndentationError: unexpected indent (file.py, line X)"
    match = re.search(r'line (\d+)', result.stderr)
    if match:
        line_num = int(match.group(1))
        error_type = "unexpected indent" if "unexpected" in result.stderr else "unknown"
        return (line_num, error_type, None)
    
    return None

def fix_indentation_smart(filepath: Path, max_attempts: int = 20) -> bool:
    """Corrige indentação baseado no contexto."""
    
    for attempt in range(max_attempts):
        error = get_compile_error(filepath)
        
        if error is None:
            print(f"  ✅ {filepath.name}: Compilando sem erros!")
            return True
        
        line_num, error_msg, context_keyword = error
        print(f"  ⚠️  {filepath.name}:{line_num} - {error_msg}")
        
        content = filepath.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        if line_num > len(lines) or line_num < 1:
            print(f"  ❌ Linha {line_num} fora do range")
            return False
        
        # Pega a linha problemática e a anterior
        problem_line = lines[line_num - 1]
        prev_line = lines[line_num - 2] if line_num > 1 else ""
        
        # Determina indentação esperada baseada no contexto
        if context_keyword in ['try', 'except', 'for', 'if', 'elif', 'else', 'while', 'with', 'def', 'class']:
            # Encontra indentação da linha anterior (que tem o ':' no final)
            prev_indent = len(prev_line) - len(prev_line.lstrip())
            expected_indent = prev_indent + 8  # Adiciona um nível
            
            # Se a linha problemática estiver vazia ou mal indentada
            stripped = problem_line.strip()
            if stripped and not stripped.startswith('#'):
                # Se for 'pass' ou similar, mantém
                if stripped in ['pass', '...', 'Ellipsis']:
                    lines[line_num - 1] = ' ' * expected_indent + stripped
                else:
                    lines[line_num - 1] = ' ' * expected_indent + stripped
                print(f"    → Fix: linha {line_num} indentada com {expected_indent} espaços")
            elif not stripped:
                # Linha vazia após contexto - adiciona 'pass'
                lines[line_num - 1] = ' ' * expected_indent + 'pass'
                print(f"    → Fix: adicionado 'pass' na linha {line_num}")
        
        elif error_msg == "unexpected indent":
            # Remove indentação extra
            stripped = problem_line.lstrip()
            if stripped:
                # Tenta manter indentação da linha anterior
                prev_indent = len(prev_line) - len(prev_line.lstrip())
                lines[line_num - 1] = ' ' * prev_indent + stripped
                print(f"    → Fix: removido indent extra da linha {line_num}")
        
        # Reescreve arquivo
        filepath.write_text('\n'.join(lines), encoding='utf-8')
    
    # Verificação final
    final_error = get_compile_error(filepath)
    return final_error is None

def main():
    print("🔧 Correção Inteligente de Indentação\n")
    
    # Todos os agents
    all_agents = [f.stem for f in AGENTS_DIR.glob("*.py") if f.stem not in ["__init__", "agent_base"]]
    
    fixed = []
    failed = []
    skipped = []
    
    for agent_name in all_agents:
        filepath = AGENTS_DIR / f"{agent_name}.py"
        
        # Verifica se tem erro
        error = get_compile_error(filepath)
        if error is None:
            skipped.append(agent_name)
            continue
        
        print(f"\n📝 {agent_name}:")
        
        if fix_indentation_smart(filepath):
            fixed.append(agent_name)
        else:
            failed.append(agent_name)
            print(f"  ❌ Não foi possível corrigir após múltiplas tentativas")
    
    print(f"\n{'='*70}")
    print(f"📊 Resumo:")
    print(f"   ✅ Corrigidos: {len(fixed)}")
    print(f"   ⚠️  Skipados (sem erro): {len(skipped)}")
    print(f"   ❌ Falharam: {len(failed)}")
    
    if failed:
        print(f"\n⚠️  Agents que precisam de correção manual:")
        for name in failed:
            print(f"   - {name}")
        return 1
    
    print(f"\n🎉 Todos os agents estão compilando corretamente!")
    return 0

if __name__ == "__main__":
    sys.exit(main())