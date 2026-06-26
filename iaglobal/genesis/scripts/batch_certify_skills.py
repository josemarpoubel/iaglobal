#!/usr/bin/env python3
# 🧬 CERTIFICADOR EM LOTE DE SKILLS (Skill Nodes) - Genesis Gatekeeper
# 
# Este script certifica TODAS as skills/nodes do iaglobal no sistema de linhagem.
# Cada skill receberá um DNA SHA3-512 único baseado em seu código-fonte.

import sys
import importlib.util
from pathlib import Path
from datetime import datetime, timezone

# Adiciona o pacote ao path
sys.path.insert(0, str(Path("/workspace")))

from iaglobal.genesis.genesis_gatekeeper import gatekeeper, certify_birth
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal")

# Caminhos para diretórios de skills
SKILLS_DIRS = [
    Path("/workspace/iaglobal/graphs"),  # SkillNode e outros nodes
    Path("/workspace/iaglobal/evolution/skills"),  # Skills de evolução
]


def load_skill_class(skill_file: Path):
    """Carrega dinamicamente a classe principal de um arquivo de skill."""
    module_name = skill_file.stem
    spec = importlib.util.spec_from_file_location(module_name, skill_file)
    if spec is None or spec.loader is None:
        return None
    
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.debug(f"⚠️ Erro ao carregar {module_name}: {e}")
        return None
    
    # Tenta encontrar a classe principal
    # Prioriza classes que terminam com "Node", "Skill", ou "Engine"
    priority_keywords = ["Node", "Skill", "Engine", "Strategy"]
    
    for keyword in priority_keywords:
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and keyword in attr_name:
                return attr
    
    # Fallback: primeira classe encontrada (exceto exceções e tipos básicos)
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (isinstance(attr, type) and 
            not attr_name.startswith("_") and 
            attr_name not in ["Exception", "BaseException"]):
            return attr
    
    return None


def certify_all_skills():
    """Certifica todas as skills nos diretórios configurados."""
    print("\n" + "="*80)
    print("🧬 CERTIFICADOR DE LINHAGEM - SKILLS IAGLOBAL")
    print("="*80 + "\n")
    
    # Primeiro, verifica a gênese primordial
    print("⚖️ Verificando gênese primordial...")
    if not gatekeeper.verify_genesis_once():
        print("🚨 ERRO CRÍTICO: Gênese violada! Abortando certificação.")
        return False
    
    print("✅ Gênese validada com sucesso!\n")
    
    # Coleta todos os arquivos de skills
    skill_files = []
    for skills_dir in SKILLS_DIRS:
        if skills_dir.exists():
            skill_files.extend(sorted(skills_dir.glob("*.py")))
    
    # Filtra __init__.py e arquivos de teste
    skill_files = [f for f in skill_files if f.name not in ["__init__.py", "test_*.py"]]
    
    print(f"📂 Encontrados {len(skill_files)} arquivos de skills em {len(SKILLS_DIRS)} diretórios\n")
    
    certified_count = 0
    failed_count = 0
    skipped_count = 0
    
    results = []
    
    for skill_file in skill_files:
        skill_name = skill_file.stem
        
        print(f"🔍 Processando {skill_name}...", end=" ")
        
        # Carrega a classe da skill
        skill_class = load_skill_class(skill_file)
        
        if skill_class is None:
            print("⚠️ SKIPPED (classe não encontrada)")
            skipped_count += 1
            results.append({
                "name": skill_name,
                "status": "skipped",
                "reason": "Classe não encontrada"
            })
            continue
        
        # Certifica a skill
        try:
            certificate = certify_birth(
                skill_class, 
                version="1.0.0",
                metadata={
                    "source_file": str(skill_file),
                    "certified_by": "batch_certify_skills.py",
                    "certification_date": datetime.now(timezone.utc).isoformat()
                }
            )
            
            print(f"✅ CERTIFIED (DNA: {certificate['dna'][:16]}...)")
            certified_count += 1
            results.append({
                "name": skill_name,
                "status": "certified",
                "dna": certificate['dna'],
                "type": certificate['component_type'],
                "version": certificate['version']
            })
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed_count += 1
            results.append({
                "name": skill_name,
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
    print(f"📈 Total:       {len(skill_files)}")
    
    # Resumo por tipo
    summary = gatekeeper.get_certified_components_summary()
    print(f"\n📊 Componentes na árvore de integridade: {summary['total_components']}")
    print(f"   Por tipo: {summary['by_type']}")
    print(f"   Por status: {summary['by_status']}")
    
    print("\n" + "="*80)
    print("🎉 CERTIFICAÇÃO DE SKILLS CONCLUÍDA!")
    print("="*80 + "\n")
    
    return True


if __name__ == "__main__":
    success = certify_all_skills()
    sys.exit(0 if success else 1)
