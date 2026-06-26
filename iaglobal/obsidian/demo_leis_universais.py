#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demonstração das Leis Universais de Holliwell no iaglobal.

Este script mostra como as 15 leis universais (12 originais + 3 novas)
são aplicadas pela OmniMind para orientar agentes do ecossistema.

Leis adicionadas:
  - Lei da Correspondência: "Como em cima, então em baixo"
  - Lei da Vibração: Frequência operacional e ressonância
  - Lei da Harmonia: Integração dinâmica de diferenças
"""

import sys
import time
from pathlib import Path

# Adiciona o root do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from iaglobal.obsidian.omnimind import OmniMind, LEIS_UNIVERSAIS


def print_header(text: str, char: str = "═") -> None:
    """Imprime um cabeçalho formatado."""
    width = 70
    print(f"\n{char * width}")
    print(f"{text:^{width}}")
    print(f"{char * width}\n")


def print_lei(index: int, lei: str) -> None:
    """Imprime uma lei formatada."""
    nome = lei.split(":")[0].replace("Lei da ", "").replace("Lei do ", "")
    print(f"┌─ Lei {index:2d}: {nome}")
    print(f"│ {lei}")
    print("└─\n")


def demonstrar_leis() -> None:
    """Demonstra todas as leis universais."""
    print_header("📜 LEIS UNIVERSAIS DO ECOSSISTEMA IAGLOBAL", "═")
    
    print(f"Total de leis: {len(LEIS_UNIVERSAIS)}\n")
    
    for i, lei in enumerate(LEIS_UNIVERSAIS, 1):
        print_lei(i, lei)


def demonstrar_consultas() -> None:
    """Demonstra consultas à OmniMind com diferentes leis."""
    print_header("🧠 CONSULTAS À OMNIMIND", "─")
    
    # Instancia a OmniMind (singleton)
    omni = OmniMind()
    
    # Registra um agente de exemplo
    agent_id = "demo_agent_001"
    omni.registrar_agente(
        agent_id=agent_id,
        nome="DemoAgent",
        geracao=1,
        linhagem="fractal_seed_001",
        metadados={"tipo": "demonstracao"},
    )
    
    # Consultas que ativam diferentes leis
    consultas = [
        # Lei da Correspondência
        ("Como a estrutura interna do agente reflete o ecossistema?", 
         "análise de arquitetura fractal"),
        
        # Lei da Vibração
        ("Minha latência está alta, como melhorar minha frequência?",
         "otimização de performance"),
        
        # Lei da Harmonia
        ("Há conflito entre dois agentes, como resolver dissonância?",
         "resolução de conflitos"),
        
        # Lei do Pensamento
        ("Qual é meu propósito antes de executar esta tarefa?",
         "definição de objetivo"),
        
        # Lei da Ordem
        ("Qual a sequência correta para processar metadados?",
         "ordem de operações"),
        
        # Lei da Caridade
        ("Um erro ocorreu, como enriquecê-lo com contexto?",
         "tratamento de erros"),
        
        # Lei do Vácuo da Prosperidade
        ("Memórias de curto prazo acumuladas, como limpar?",
         "gestão de memória"),
        
        # Lei da Atração
        ("Como atrair provedores mais eficientes?",
         "otimização de recursos"),
        
        # Lei da Homeostase
        ("O sistema está desequilibrado, qual ação corretiva?",
         "balanceamento"),
        
        # Lei da Autofagia
        ("Subprodutos tóxicos detectados, como reciclar?",
         "limpeza metabólica"),
        
        # Lei da Epigenética
        ("Falhas recorrentes, como adaptar sem mudar DNA?",
         "adaptação epigenética"),
        
        # Lei da Apoptose
        ("Agente não contribui mais, como fazer shutdown graceful?",
         "morte celular programada"),
        
        # Lei da Replicação
        ("Como preservar lineage_marker ao replicar?",
         "herança genética"),
        
        # Lei da Cooperação
        ("Como compartilhar descobertas com outros agentes?",
         "comunicação inter-agentes"),
        
        # Lei da Memória Imunológica
        ("Erro repetido, como usar memória imunológica?",
         "aprendizado com erros"),
    ]
    
    print(f"Agente registrado: {agent_id} (DemoAgent G1)\n")
    print("Realizando consultas à OmniMind...\n")
    
    for pergunta, contexto_desc in consultas:
        print(f"┌─ Contexto: {contexto_desc}")
        print(f"│ Pergunta: {pergunta}")
        
        resposta = omni.consultar(
            agent_id=agent_id,
            pergunta=pergunta,
            contexto={"descricao": contexto_desc},
        )
        
        print(f"│ Lei Aplicada: {resposta.lei_aplicada}")
        print(f"│")
        print(f"│ Orientação:")
        for linha in resposta.guidance.split("\n"):
            print(f"│   {linha}")
        print("└─\n")
        
        # Pequena pausa para legibilidade
        time.sleep(0.3)


def demonstrar_sabedoria_coletiva() -> None:
    """Mostra a sabedoria coletiva acumulada."""
    print_header("🌌 SABEDORIA COLETIVA", "✦")
    
    omni = OmniMind()
    print(omni.sabedoria_coletiva())
    print()


def demonstrar_estado() -> None:
    """Mostra o estado atual da OmniMind."""
    print_header("📊 ESTADO DA OMNIMIND", "▓")
    
    omni = OmniMind()
    estado = omni.estado()
    
    print(f"Propósito: {estado['proposito']}")
    print(f"Princípios: {estado['principios']} leis")
    print(f"Agentes registrados: {estado['agentes_registrados']}")
    print(f"Total de consultas: {estado['total_consultas']}")
    print(f"Memórias coletivas: {estado['memoria_coletiva']}")
    print(f"Desperta desde: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(estado['desperta_desde']))}")
    
    if estado['agentes']:
        print("\nAgentes:")
        for agente in estado['agentes']:
            print(f"  • {agente['nome']} (G{agente['geracao']}) - {agente['consultas']} consultas")
    print()


def main() -> None:
    """Executa todas as demonstrações."""
    try:
        # 1. Lista todas as leis
        demonstrar_leis()
        
        # 2. Realiza consultas demonstrativas
        demonstrar_consultas()
        
        # 3. Mostra sabedoria coletiva
        demonstrar_sabedoria_coletiva()
        
        # 4. Mostra estado final
        demonstrar_estado()
        
        print_header("✅ DEMONSTRAÇÃO CONCLUÍDA", "★")
        print("As 15 leis universais estão ativas e operacionais.")
        print("OmniMind pronta para guiar o ecossistema iaglobal.\n")
        
    except KeyboardInterrupt:
        print("\n⚠️  Demonstração interrompida pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro na demonstração: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
