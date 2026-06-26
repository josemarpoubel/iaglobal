#!/usr/bin/env python3
"""
Demo: Sistema de Linhagem Genética (Genesis Gatekeeper)

Demonstra como o DNA SHA3-512 é usado para garantir integridade
de agentes e skills ao longo do tempo.
"""

import sys
import os

# Adiciona o projeto ao path
sys.path.insert(0, os.path.abspath('.'))

from iaglobal.core.genesis_gatekeeper import get_gatekeeper
from iaglobal.agents.coder_agent import CoderAgent
# Nota: Não importamos RegeneratorAgent aqui para evitar circular imports
# Ele será testado indiretamente através do ImmuneOrchestrator
from iaglobal.graphs.skill_node import SkillNode
from iaglobal.evolution.skills.dynamic_registry import dynamic_registry

print("=" * 80)
print("🧬 DEMO: SISTEMA DE LINHAGEM GENÉTICA (GENESIS GATEKEEPER)")
print("=" * 80)
print()

# --- 1. Inicialização do Gatekeeper ---
print("1️⃣  INICIALIZANDO GENESIS GATEKEEPER...")
print("-" * 80)
gatekeeper = get_gatekeeper()
print(f"✓ Gatekeeper inicializado em: {gatekeeper.genesis_path}")
print(f"✓ Componentes registrados: {len(gatekeeper.dna_registry['components'])}")
print()

# --- 2. Registro/Verificação de Agentes ---
print("2️⃣  VERIFICANDO LINHAGEM DE AGENTES...")
print("-" * 80)

print("\n🤖 CoderAgent:")
try:
    coder = CoderAgent(temperatura=0.5, estilo="direto")
    print("   ✓ Agente instanciado com sucesso")
except Exception as e:
    print(f"   ⚠ Erro na instanciação: {e}")

print()

# --- 3. Verificação de Skills ---
print("3️⃣  VERIFICANDO LINHAGEM DE SKILLS...")
print("-" * 80)

# Nota: A verificação de DNA de skills já ocorre automaticamente no SkillNode
# quando uma skill é executada. Para esta demo, apenas mostramos o conceito.

print("\nℹ️  Skills são verificadas automaticamente durante execução via SkillNode")
print("   Exemplo de log acima: '✓ SkillNode lineage verified'")
print()

# --- 4. Consulta de Linhagem ---
print("4️⃣  CONSULTANDO LINHAGEM REGISTRADA...")
print("-" * 80)

registered_components = gatekeeper.dna_registry['components']
for component_id, data in list(registered_components.items())[:5]:  # Mostra primeiros 5
    print(f"\n📄 Componente: {component_id}")
    print(f"   Tipo: {data.get('type', 'N/A')}")
    print(f"   Versão: {data.get('version', 'N/A')}")
    print(f"   DNA: {data.get('dna', 'N/A')[:32]}...")
    print(f"   Registrado em: {data.get('registered_at', 'N/A')}")

print()

# --- 5. Teste de Detecção de Mutação ---
print("5️⃣  TESTE: DETECÇÃO DE MUTAÇÃO NÃO AUTORIZADA...")
print("-" * 80)

test_component_id = "test.mutation_detector"
test_source_v1 = "def original_function(): return 1"
test_source_v2 = "def mutated_function(): return 2  # MUTATION!"

print(f"\n🔒 Registrando componente original...")
dna_v1 = gatekeeper.register_component(
    component_id=test_component_id,
    source_code=test_source_v1,
    component_type="test",
    version="1.0.0"
)
print(f"   DNA original: {dna_v1[:32]}...")

print(f"\n🔍 Tentando verificar versão mutada...")
try:
    gatekeeper.verify_dna(
        component_id=test_component_id,
        source_code=test_source_v2,
        component_type="test",
        version="1.0.0"
    )
    print("   ❌ ERRO: Mutação não detectada!")
except ValueError as e:
    print(f"   ✓ MUTAÇÃO DETECTADA COM SUCESSO!")
    print(f"   Mensagem: {str(e)[:100]}...")

print()

# --- 6. Dashboard Final ---
print("6️⃣  DASHBOARD FINAL DO GENESIS GATEKEEPER")
print("-" * 80)

total_components = len(registered_components)
agents_count = sum(1 for c in registered_components.values() if c['type'].startswith('agent:'))
skills_count = sum(1 for c in registered_components.values() if c['type'] == 'skill')
test_count = sum(1 for c in registered_components.values() if c['type'] == 'test')

print(f"""
┌─────────────────────────────────────────────────────────────┐
│  🧬 GENESIS GATEKEEPER - STATUS                             │
├─────────────────────────────────────────────────────────────┤
│  Total de Componentes:     {total_components:>5}                    │
│  ├─ Agents:                {agents_count:>5}                    │
│  ├─ Skills:                {skills_count:>5}                    │
│  └─ Test/Demo:             {test_count:>5}                    │
├─────────────────────────────────────────────────────────────┤
│  Hash Algorithm:           SHA3-512                           │
│  Imutable Log:             lineage_log.jsonl                  │
│  Registry File:            dna_registry.json                  │
└─────────────────────────────────────────────────────────────┘
""")

print("=" * 80)
print("✅ DEMO CONCLUÍDA COM SUCESSO!")
print("=" * 80)
print()
print("📝 Próximos passos:")
print("   • Todos os novos agentes serão automaticamente registrados")
print("   • Qualquer modificação não autorizada será detectada")
print("   • Histórico completo disponível em lineage_log.jsonl")
print()
