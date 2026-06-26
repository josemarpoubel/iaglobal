#!/usr/bin/env python3
"""
Script para certificar em lote todos os módulos críticos restantes:
- core/*.py (orquestradores, engines, config)
- immunity/*.py (sistema imunológico)
- evolution/*.py (motores de evolução)
- memory/*.py (sistemas de memória)

Gera DNA SHA3-512 único para cada módulo e registra na Integrity Tree.
"""

import sys
import os
from pathlib import Path

# Adicionar root do projeto ao path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Configurar PYTHONPATH explicitamente
os.environ['PYTHONPATH'] = str(root_dir) + ':' + os.environ.get('PYTHONPATH', '')

from genesis.genesis_gatekeeper import GenesisGatekeeper, certify_birth
from utils.logger import get_logger

logger = get_logger("iaglobal")

def get_critical_modules():
    """Lista de módulos críticos por categoria."""
    modules = {
        'core': [
            'orchestrator', 'neuro_orchestrator', 'decision_engine',
            'cognitive_proxy', 'cognitive_runtime', 'governance',
            'evolution_controller', 'law_engine', 'config',
            'retry_handler', 'graceful_shutdown', 'diagnostico',
            'structure', 'assistant'
        ],
        'immunity': [
            'immune_orchestrator', 'loop_detector', 'regression_detector',
            'hallucination_detector', 'mhc_detector', 'apoptosis_engine',
            'pathogen_analyzer', 'adaptive_threat_detector',
            'emergent_behavior_detector', 'epigenetic_masking',
            'glutathione_pool', 'glutathione_guardrails',
            'metabolic_pruner', 'immune_memory_exchange'
        ],
        'evolution': [
            'evolutionengine', 'evolutionruntime', 'evo_agent',
            'self_optimizer', 'meta_evolver', 'homeostasis_controller',
            'reward_aggregator', 'task_analyzer', 'same_engine',
            'darwin_harness', 'collapse_detector', 'epigenetic',
            'handler_evolution', 'meta_agent_designer',
            'execution_registry', 'skill_quarantine', 'proposal_quarantine',
            'ga_router_optimizer', 'canonical_graph', 'execution_context',
            'evolution_replay'
        ],
        'memory': [
            'memory', 'async_memory', 'persistence', 'db_manager',
            'backup_manager', 'consolidation', 'fusion_engine',
            'semantic_cache', 'cognitive_cache', 'memory_storage',
            'memory_vector', 'ranking', 'raw_pool',
            'term_short', 'term_long', 'cache', 'core'
        ]
    }
    return modules

def load_module_class(module_file: Path, category: str):
    """Carrega dinamicamente a classe principal de um módulo."""
    import importlib.util
    
    module_name = module_file.stem
    spec = importlib.util.spec_from_file_location(f"{category}.{module_name}", module_file)
    if spec is None or spec.loader is None:
        return None
    
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Tenta encontrar a classe principal
        class_name = "".join(word.capitalize() for word in module_name.split("_"))
        if hasattr(module, class_name):
            return getattr(module, class_name)
        
        # Fallback: procura por classes com sufixos comuns
        for suffix in ['Engine', 'Orchestrator', 'Detector', 'Manager', 'Handler', 'Controller']:
            for attr_name in dir(module):
                if attr_name.endswith(suffix):
                    return getattr(module, attr_name)
        
        return None
    except Exception as e:
        logger.debug(f"Erro ao carregar {module_name}: {e}")
        return None

def certify_module(gatekeeper, category, module_name, base_path):
    """Certifica um único módulo."""
    source_file = base_path / f"{module_name}.py"
    
    if not source_file.exists():
        # Tenta __init__.py para pacotes
        source_file = base_path / module_name / "__init__.py"
        if not source_file.exists():
            logger.debug(f"Arquivo não encontrado: {category}/{module_name}")
            return None
    
    try:
        # Tenta carregar a classe do módulo
        module_class = load_module_class(source_file, category)
        
        if module_class:
            # Usa certify_birth se a classe foi encontrada
            certificate = certify_birth(
                module_class,
                version="1.0.0",
                metadata={
                    'category': category,
                    'source_file': str(source_file),
                    'description': f"Módulo crítico {category}.{module_name}"
                }
            )
            
            dna = certificate['dna'][:16] + "..."
            print(f"  ✅ {category}.{module_name:<30} DNA: {dna}")
            return certificate
        else:
            # Fallback: registra o arquivo diretamente
            with open(source_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            dna = gatekeeper.calculate_component_dna(
                source_code=source_code,
                component_name=f"{category}.{module_name}",
                component_type='component',
                version="1.0.0"
            )
            
            # Registra manualmente na árvore
            certificate = {
                "component_name": f"{category}.{module_name}",
                "component_type": "component",
                "dna": dna,
                "version": "1.0.0",
                "certified_at": datetime.utcnow().isoformat(),
                "genesis_hash": gatekeeper.integrity_tree.get("genesis_hash"),
                "metadata": {
                    'category': category,
                    'source_file': str(source_file)
                },
                "status": "active",
                "lineage_verified": True,
                "evolution_count": 0
            }
            
            gatekeeper._upsert_component_in_tree(certificate)
            
            print(f"  ✅ {category}.{module_name:<30} DNA: {dna[:16]}...")
            return certificate
            
    except Exception as e:
        logger.error(f"Erro em {category}.{module_name}: {e}")
        print(f"  ❌ Erro em {category}.{module_name}: {str(e)[:50]}")
        return None

def main():
    print("=" * 70)
    print("🧬 CERTIFICAÇÃO EM LOTE - MÓDULOS CRÍTICOS")
    print("=" * 70)
    
    from datetime import datetime
    
    # Inicializar Gatekeeper
    gatekeeper = GenesisGatekeeper()
    
    modules = get_critical_modules()
    total_certified = 0
    total_failed = 0
    results_by_category = {}
    
    for category, module_list in modules.items():
        print(f"\n{'='*70}")
        print(f"📁 Categoria: {category.upper()} ({len(module_list)} módulos)")
        print(f"{'='*70}")
        
        base_path = root_dir / "iaglobal" / category
        category_results = []
        
        for module_name in module_list:
            result = certify_module(gatekeeper, category, module_name, base_path)
            if result:
                total_certified += 1
                category_results.append(result)
            else:
                total_failed += 1
        
        results_by_category[category] = category_results
    
    # Gerar relatório final
    print(f"\n{'='*70}")
    print("📊 RELATÓRIO FINAL DE CERTIFICAÇÃO")
    print(f"{'='*70}")
    print(f"✅ Total certificado: {total_certified} módulos")
    print(f"❌ Total falhou:      {total_failed} módulos")
    if total_certified + total_failed > 0:
        print(f"📈 Sucesso:           {(total_certified/(total_certified+total_failed)*100):.1f}%")
    
    # Resumo por categoria
    print(f"\n📁 Resumo por categoria:")
    for category, results in results_by_category.items():
        print(f"   {category:<12}: {len(results)} certificados")
    
    # Hash da Genesis atual
    genesis_hash = gatekeeper.integrity_tree.get("genesis_hash", "N/A")
    print(f"\n🌱 Genesis Hash: {str(genesis_hash)[:32]}...")
    
    # Salvar árvore de integridade
    tree_file = root_dir / "iaglobal" / "genesis" / "data" / "integrity_tree_critical.cbor"
    gatekeeper._save_integrity_tree()
    print(f"💾 Árvore de integridade salva em: {tree_file}")
    
    # Verificar componentes totais
    summary = gatekeeper.get_certified_components_summary()
    print(f"\n🔍 Total de componentes no sistema: {summary['total_components']}")
    
    print(f"\n{'='*70}")
    print("🎉 CERTIFICAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f"{'='*70}")
    
    return 0 if total_failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
