#!/usr/bin/env python3
"""
Script de refatoração em massa: Converte agents para usar AgentBase.

Uso: python scripts/refactor_agents.py
"""

import os
import re
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent / "iaglobal" / "agents"

AGENTS_TO_REFACTOR = [
    "critic_agent",
    "debugger_agent",
    "dependency_agent",
    "enhancement_agent",
    "evolution_agent",
    "failure_analysis_agent",
    "intent_classifier_agent",
    "knowledge_writer_agent",
    "multi_agent",
    "orchestrator_agent",
    "performance_audit_agent",
    "performance_design_agent",
    "pm_agent",
    "reflexion_agent",
    "requirements_agent",
    "result_agent",
    "search_agent",
    "security_audit_agent",
    "security_design_agent",
    "skill_generator_agent",
    "typing_agent",
    "validator",
]

def refactor_agent_file(filepath: Path) -> bool:
    """Refatora um arquivo de agent para usar AgentBase."""
    
    content = filepath.read_text(encoding='utf-8')
    original = content
    
    # 1. Adiciona import do AgentBase se não existir
    if "from iaglobal.agents.agent_base import AgentBase" not in content:
        # Encontra imports existentes e adiciona após
        import_match = re.search(r'(from iaglobal\.[\w.]+ import .*\n)', content)
        if import_match:
            insert_pos = import_match.end()
            content = content[:insert_pos] + "from iaglobal.agents.agent_base import AgentBase\n" + content[insert_pos:]
    
    # 2. Remove imports desnecessários de bandit
    content = re.sub(r'from iaglobal\.graphs\.bandit import .*?\n', '', content)
    content = re.sub(r'from iaglobal\.graphs\.credit import .*?\n', '', content)
    
    # 3. Muda a classe para herdar de AgentBase
    content = re.sub(
        r'class (\w+Agent):',
        r'class \1(AgentBase):',
        content
    )
    
    # 4. Adiciona super().__init__() no __init__ se não existir
    init_match = re.search(r'def __init__\(self[^\)]*\):\s*\n(\s+)([^#\n])', content)
    if init_match and "super().__init__" not in content:
        indent = init_match.group(1)
        # Encontra o nome da classe
        class_match = re.search(r'class (\w+Agent)', content)
        if class_match:
            agent_name = class_match.group(1).replace('Agent', '').lower().replace('_', '')
            super_init = f"super().__init__(agent_name=\"{agent_name}\")\n{indent}"
            # Insere após o __init__
            content = content[:init_match.end()-1] + super_init + content[init_match.end()-1:]
    
    # 5. Substitui self.bandit = _get_bandit() por nada (já herdado)
    content = re.sub(r'\s+self\.bandit = _get_bandit\(\)\n', '\n', content)
    content = re.sub(r'\s+self\.credit = CreditAssignmentEngine\(\)\n', '\n', content)
    
    # 6. Substitui self.bandit.select_model por self._call_llm (mais complexo - requer ajuste manual)
    # Deixamos isso para revisão manual
    
    # Escreve de volta se mudou
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    print("🔧 Refatorando agents para usar AgentBase...\n")
    
    refactored = []
    skipped = []
    errors = []
    
    for agent_name in AGENTS_TO_REFACTOR:
        filepath = AGENTS_DIR / f"{agent_name}.py"
        
        if not filepath.exists():
            skipped.append(f"{agent_name} (arquivo não encontrado)")
            continue
        
        try:
            if refactor_agent_file(filepath):
                refactored.append(agent_name)
                print(f"✅ {agent_name}")
            else:
                skipped.append(f"{agent_name} (sem mudanças)")
        except Exception as e:
            errors.append(f"{agent_name}: {e}")
            print(f"❌ {agent_name}: {e}")
    
    print(f"\n📊 Resumo:")
    print(f"   ✅ Refatorados: {len(refactored)}")
    print(f"   ⚠️  Skipados: {len(skipped)}")
    print(f"   ❌ Erros: {len(errors)}")
    
    if errors:
        print(f"\n⚠️  Agents com erro:")
        for err in errors:
            print(f"   - {err}")

if __name__ == "__main__":
    main()