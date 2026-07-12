#!/usr/bin/env python3
"""
Dashboard da BanditPolicy Evolutiva - Geração 2

Monitora em tempo real:
- Fitness score de cada provider
- IVM médio histórico
- Banimentos ativos
- Evolução de weights
- Distribuição de seleções

Uso:
    python3 scripts/bandit_evolutiva_dashboard.py
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from collections import Counter


def carregar_estado():
    """Carrega estado da BanditPolicyEvolutiva."""
    db_path = Path("iaglobal/memory/bandit_evolutivo.json")
    if not db_path.exists():
        return None
    
    with open(db_path, "r", encoding="utf-8") as f:
        return json.load(f)


def formatar_datetime(iso_string):
    """Formata datetime ISO para legível."""
    if not iso_string:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%d/%m %H:%M")
    except:
        return iso_string


def dashboard():
    """Exibe dashboard da evolução."""
    print("=" * 70)
    print("🧬 DASHBOARD DA BANDITPOLICY EVOLUTIVA - GERAÇÃO 2")
    print("=" * 70)
    print()
    
    estado = carregar_estado()
    
    if not estado:
        print("⚠️  Nenhum estado evolutivo encontrado.")
        print()
        print("Para ativar:")
        print("  1. Export USE_BANDIT_EVOLUTIVA=true")
        print("  2. Rode tarefas reais com providers")
        print("  3. Execute este dashboard novamente")
        return
    
    # Informações gerais
    atualizado_em = estado.get("updated_at", "N/A")
    fitness_records = estado.get("fitness_records", {})
    banned = estado.get("banned_providers", {})
    weights = estado.get("weights", {})
    
    print(f"📅 Última atualização: {formatar_datetime(atualizado_em)}")
    print(f"📊 Providers registrados: {len(fitness_records)}")
    print(f"🚫 Providers banidos: {len(banned)}")
    print()
    
    # Tabela de fitness
    print("📈 FITNESS DOS PROVIDERS:")
    print("-" * 70)
    print(f"{'Provider':<30} {'Fitness':<10} {'IVM Médio':<10} {'Usos':<8} {'Sucessos':<10}")
    print("-" * 70)
    
    providers_ordenados = sorted(
        fitness_records.items(),
        key=lambda x: x[1].get("fitness_score", 0),
        reverse=True
    )
    
    for provider_id, dados in providers_ordenados:
        fitness = dados.get("fitness_score", 0)
        ivm_medio = dados.get("ivm_media_movel", 0)
        total_uses = dados.get("total_uses", 0)
        successful = dados.get("successful_uses", 0)
        
        # Cor baseada no fitness
        if fitness >= 0.7:
            status = "🟢"
        elif fitness >= 0.5:
            status = "🟡"
        else:
            status = "🔴"
        
        print(f"{status} {provider_id[:28]:<30} {fitness:<10.3f} {ivm_medio:<10.3f} {total_uses:<8} {successful:<10}")
    
    print()
    
    # Banimentos
    if banned:
        print("🚫 BANIMENTOS ATIVOS:")
        print("-" * 70)
        print(f"{'Provider':<30} {'Banido até':<20} {'Motivo':<20}")
        print("-" * 70)
        
        agora = datetime.now()
        for provider, ban_until_str in banned.items():
            try:
                ban_until = datetime.fromisoformat(ban_until_str)
                restante = ban_until - agora
                horas_restantes = restante.total_seconds() / 3600
                
                if horas_restantes > 0:
                    print(f"🚫 {provider[:28]:<30} {formatar_datetime(ban_until_str):<20} {horas_restantes:.1f}h restantes")
            except:
                print(f"🚫 {provider[:28]:<30} {ban_until_str:<20} (erro)")
        
        print()
    
    # Weights
    if weights:
        print("⚖️  WEIGHTS ATUAIS:")
        print("-" * 70)
        weights_ordenados = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        
        for provider, weight in weights_ordenados[:10]:  # Top 10
            barra = "█" * int(weight * 10)
            print(f"{provider[:28]:<30} {weight:.3f} {barra}")
        
        print()
    
    # Estatísticas
    if fitness_records:
        fitness_scores = [d.get("fitness_score", 0) for d in fitness_records.values()]
        ivm_medias = [d.get("ivm_media_movel", 0) for d in fitness_records.values()]
        
        print("📊 ESTATÍSTICAS GERAIS:")
        print("-" * 70)
        print(f"  Fitness médio:     {sum(fitness_scores) / len(fitness_scores):.3f}")
        print(f"  Fitness máximo:    {max(fitness_scores):.3f}")
        print(f"  Fitness mínimo:    {min(fitness_scores):.3f}")
        print(f"  IVM médio histórico: {sum(ivm_medias) / len(ivm_medias):.3f}")
        print(f"  Total de execuções:  {sum(d.get('total_uses', 0) for d in fitness_records.values())}")
        print()
    
    # Top providers
    if providers_ordenados:
        print("🏆 TOP 3 PROVIDERS:")
        print("-" * 70)
        for i, (provider, dados) in enumerate(providers_ordenados[:3], 1):
            medalha = ["🥇", "🥈", "🥉"][i-1]
            fitness = dados.get("fitness_score", 0)
            print(f"  {medalha} {i}º {provider}: {fitness:.3f}")
        print()
    
    print("=" * 70)
    print()
    
    # Informações de uso
    print("💡 DICAS:")
    print("  - Para ativar: export USE_BANDIT_EVOLUTIVA=true")
    print("  - Para desativar: export USE_BANDIT_EVOLUTIVA=false")
    print("  - Dados são persistidos em: iaglobal/memory/bandit_evolutivo.json")
    print("  - Execute `iaglobal run \"tarefa\"` para gerar dados de evolução")
    print()


def monitoramento_contínuo(intervalo_segundos=10):
    """Dashboard em tempo real com atualização automática."""
    print(f"🔄 Iniciando monitoramento contínuo (atualiza a cada {intervalo_segundos}s)")
    print("Pressione Ctrl+C para sair")
    print()
    
    try:
        while True:
            dashboard()
            asyncio.run(asyncio.sleep(intervalo_segundos))
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoramento interrompido pelo usuário")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        monitoramento_contínuo()
    else:
        dashboard()