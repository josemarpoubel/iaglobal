# iaglobal/integration_registry.py
"""Registro de integrações entre módulos novos e o ecossistema iaglobal.

Objetivo:
- Mapear dependências explícitas entre novos módulos e o pipeline.
- Garantir que nenhuma função fique órfã.
- Facilitar auditoria arquitetural.
"""

from typing import Dict, Set

# Mapeia cada módulo para seus dependentes (quem o importa/utiliza)
INTEGRACOES: Dict[str, Set[str]] = {
    # Lei do Pensamento
    "iaglobal/graphs/nodes/no_law_of_thought_enforcer.py": {
        "iaglobal/graphs/topology.py",  # Executado no pipeline
        "iaglobal/obsidian/omnimind.py",  # Registra violações
        "iaglobal/obsidian/epigenetic_registry.py",  # Armazena violações
    },
    # Força para a Lei do Vácuo
    "iaglobal/graphs/nodes/no_vacuum_strength.py": {
        "iaglobal/graphs/topology.py",  # Executado no pipeline
        "iaglobal/obsidian/omnimind.py",  # Emite gatilho de vácuo
        "iaglobal/obsidian/epigenetic_registry.py",  # Injeta nutrientes
    },
    # Direção Autônoma (ClarityDirective)
    "iaglobal/graphs/nodes/no_clarity_directive.py": {
        "iaglobal/graphs/topology.py",  # Executado no pipeline
        "iaglobal/obsidian/epigenetic_registry.py",  # Marca tarefas para clareamento
    },
    # Compartimento de Fuga
    "iaglobal/graphs/nodes/no_fugue_compartment.py": {
        "iaglobal/graphs/topology.py",  # Executado no pipeline
        "iaglobal/subconscious/fugue_compartment.py",  # Implementação
    },
    "iaglobal/subconscious/fugue_compartment.py": {
        "iaglobal/subconscious/subconscious_api.py",  # Registra tarefas no vault
        "iaglobal/subconscious/delta_sleep.py",  # Integração REM→Delta
        "iaglobal/dashboard/metabolic_sleep_dashboard.py",  # Métricas
    },
    # Sono Delta
    "iaglobal/subconscious/delta_sleep.py": {
        "iaglobal/subconscious/subconscious_api.py",  # Remove/compacta notas
        "iaglobal/subconscious/fugue_compartment.py",  # Sincronização
    },
    # SubconsciousAPI
    "iaglobal/subconscious/subconscious_api.py": {
        "iaglobal/obsidian/subconsciousapi.py",  # Operações reais no vault
    },
    # Dashboard de Sono
    "iaglobal/dashboard/metabolic_sleep_dashboard.py": {
        "iaglobal/subconscious/fugue_compartment.py",  # Métricas
        "iaglobal/subconscious/delta_sleep.py",  # Métricas
    },
}

# Funções que são entry points (não devem ser marcadas como órfãs)
ENTRY_POINTS = {
    "run_law_of_thought_enforcer",
    "run_vacuum_strength",
    "run_clarity_directive",
    "run_fugue_compartment",
    "processar_em_segundo_plano",  # FugueCompartment
    "limpar_toxinas",            # DeltaSleepSync
    "compactar_memoria",          # DeltaSleepSync
    "exibir_dashboard",           # MetabolicSleepDashboard
}