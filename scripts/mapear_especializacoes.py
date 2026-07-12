#!/usr/bin/env python3
"""Mapeia especializações dos 115 agents existentes."""

import os
from pathlib import Path
from collections import defaultdict

nodes_dir = Path("iaglobal/graphs/nodes")
especializacoes = defaultdict(list)

for file in nodes_dir.glob("no_*.py"):
    if "__pycache__" in str(file):
        continue
    nome = file.stem.replace("no_", "")
    
    # Categorização por palavras-chave
    if any(x in nome for x in ["coder", "code", "debug", "executor", "multi_coder"]):
        especializacoes["🧑‍💻 Código"].append(nome)
    elif any(x in nome for x in ["architect", "design", "system", "api"]):
        especializacoes["🏗️ Arquitetura"].append(nome)
    elif any(x in nome for x in ["security", "audit", "threat"]):
        especializacoes["🛡️ Segurança"].append(nome)
    elif any(x in nome for x in ["test", "qa", "validator"]):
        especializacoes["✅ Testes"].append(nome)
    elif any(x in nome for x in ["doc", "writer", "artifact", "knowledge"]):
        especializacoes["📚 Documentação"].append(nome)
    elif any(x in nome for x in ["optim", "perform", "metric"]):
        especializacoes["⚡ Performance"].append(nome)
    elif any(x in nome for x in ["database", "backend", "frontend"]):
        especializacoes["🗄️ Infra/DB"].append(nome)
    elif "evolution" in nome or "evolve" in nome:
        especializacoes["🧬 Evolução"].append(nome)
    elif "immune" in nome:
        especializacoes["🦠 Imunologia"].append(nome)
    else:
        especializacoes["🔧 Outros"].append(nome)

# Imprimir relatório
print("=" * 70)
print("🧬 MAPEAMENTO DE ESPECIALIZAÇÕES - 115 AGENTS")
print("=" * 70)
print()

total = 0
for categoria, agents in sorted(especializacoes.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"{categoria}: {len(agents)} agents")
    for agent in sorted(agents)[:8]:
        print(f"  • {agent}")
    if len(agents) > 8:
        print(f"  ... e mais {len(agents) - 8}")
    print()
    total += len(agents)

print("=" * 70)
print(f"TOTAL GERAL: {total} agents especializados")
print("=" * 70)
