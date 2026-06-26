#!/usr/bin/env python3
# 🧬 CERTIFICADOR EM LOTE DE AGENTES - Genesis Gatekeeper
# 
# Este script certifica TODOS os agentes do iaglobal no sistema de linhagem.
# Cada agente receberá um DNA SHA3-512 único baseado em seu código-fonte.

import sys
import importlib.util
from pathlib import Path
from datetime import datetime

# Adiciona o pacote ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from iaglobal.genesis.genesis_gatekeeper import gatekeeper, certify_birth
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal")

# Caminho absoluto para o diretório de agentes
AGENTS_DIR = Path("/workspace/iaglobal/agents")


def load_agent_class(agent_file: Path):
    """Carrega dinamicamente a classe principal de um arquivo de agente."""
    module_name = agent_file.stem
    spec = importlib.util.spec_from_file_location(module_name, agent_file)
    if spec is None or spec.loader is None:
        return None
    
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar {module_name}: {e}")
        return None
    
    # Tenta encontrar a classe principal (geralmente tem o mesmo nome do arquivo em PascalCase)
    class_name = "".join(word.capitalize() for word in module_name.split("_"))
    if hasattr(module, class_name):
        return getattr(module, class_name)
    
    # Fallback: procura por qualquer classe que termine com "Agent"
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and attr_name.endswith("Agent"):
            return attr
    
    return None


def certify_all_agents():
    """Certifica todos os agentes no diretório agents/."""
    print("\n" + "="*80)
    print("🧬 CERTIFICADOR DE LINHAGEM - AGENTES IAGLOBAL")
    print("="*80 + "\n")
    
    # Primeiro, verifica a gênese primordial
    print("⚖️ Verificando gênese primordial...")
    if not gatekeeper.verify_genesis_once():
        print("🚨 ERRO CRÍTICO: Gênese violada! Abortando certificação.")
        return False
    
    print("✅ Gênese validada com sucesso!\n")
    
    # Lista todos os arquivos de agentes
    agent_files = sorted(AGENTS_DIR.glob("*.py"))
    agent_files = [f for f in agent_files if f.name not in ["__init__.py"]]
    
    print(f"📂 Encontrados {len(agent_files)} arquivos de agentes\n")
    
    certified_count = 0
    failed_count = 0
    skipped_count = 0
    
    results = []
    
    for agent_file in agent_files:
        agent_name = agent_file.stem
        
        print(f"🔍 Processando {agent_name}...", end=" ")
        
        # Carrega a classe do agente
        agent_class = load_agent_class(agent_file)
        
        if agent_class is None:
            print("⚠️ SKIPPED (classe não encontrada)")
            skipped_count += 1
            results.append({
                "name": agent_name,
                "status": "skipped",
                "reason": "Classe não encontrada"
            })
            continue
        
        # Certifica o agente
        try:
            certificate = certify_birth(
                agent_class, 
                version="1.0.0",
                metadata={
                    "source_file": str(agent_file),
                    "certified_by": "batch_certifier.py",
                    "certification_date": datetime.utcnow().isoformat()
                }
            )
            
            print(f"✅ CERTIFIED (DNA: {certificate['dna'][:16]}...)")
            certified_count += 1
            results.append({
                "name": agent_name,
                "status": "certified",
                "dna": certificate['dna'],
                "type": certificate['component_type'],
                "version": certificate['version']
            })
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed_count += 1
            results.append({
                "name": agent_name,
                "status": "failed",
                "error": str(e)
            })
    
    # Resumo final
    print("\n" + "="*80)
    print("📊 RESUMO DA CERTIFICAÇÃO")
    print("="*80)
    print(f"✅ Certificados: {certified_count}")
    print(f"❌ Falharam:    {failed_count}")
    print(f"⚠️  Skipados:    {skipped_count}")
    print(f"📈 Total:       {len(agent_files)}")
    
    # Resumo por tipo
    summary = gatekeeper.get_certified_components_summary()
    print(f"\n📊 Componentes na árvore de integridade: {summary['total_components']}")
    print(f"   Por tipo: {summary['by_type']}")
    print(f"   Por status: {summary['by_status']}")
    
    print("\n" + "="*80)
    print("🎉 CERTIFICAÇÃO CONCLUÍDA!")
    print("="*80 + "\n")
    
    return True


if __name__ == "__main__":
    success = certify_all_agents()
    sys.exit(0 if success else 1)
