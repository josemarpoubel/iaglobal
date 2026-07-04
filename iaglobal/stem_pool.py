"""
Stem Agent Pool - Passo 119 do ROADMAP
Pool de agentes-tronco com diferenciação por demanda metabólica

Baseado no conceito de células-tronco biológicas:
- Mantém pool de agentes indiferenciados (stem agents)
- Diferencia sob demanda baseada em sinais metabólicos
- Especialização reversível (plasticidade)
- Homeostase do pool (auto-renovação)
"""

from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import hashlib
from datetime import datetime


class AgentType(Enum):
    """Tipos especializados de agentes"""
    CODER = "coder"
    ANALYST = "analyst"
    EXPLORER = "explorer"
    GUARDIAN = "guardian"
    OPTIMIZER = "optimizer"
    STEMMING = "stemming"  # Agente tronco não diferenciado


@dataclass
class DifferentiationSignal:
    """Sinal metabólico que trigger diferenciação"""
    signal_type: str
    intensity: float  # 0.0 a 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StemAgent:
    """Agente tronco com potencial de diferenciação"""
    agent_id: str
    base_dna: str  # DNA base comum a todos stem agents
    potential_types: List[AgentType]
    current_type: AgentType = AgentType.STEMMING
    differentiation_count: int = 0
    last_differentiation: Optional[datetime] = None
    metabolic_state: Dict[str, float] = field(default_factory=dict)
    plasticity_score: float = 1.0  # Capacidade de re-diferenciar
    
    def clone(self) -> 'StemAgent':
        """Cria cópia para divisão celular"""
        return StemAgent(
            agent_id=f"{self.agent_id}_clone_{random.randint(1000, 9999)}",
            base_dna=self.base_dna,
            potential_types=self.potential_types.copy(),
            current_type=self.current_type,
            differentiation_count=self.differentiation_count,
            last_differentiation=self.last_differentiation,
            metabolic_state=self.metabolic_state.copy(),
            plasticity_score=max(0.5, self.plasticity_score * 0.95)  # Leve redução na plasticidade
        )


class StemAgentPool:
    """
    Pool de agentes-tronco com diferenciação por demanda
    
    Responsabilidades:
    - Manter homeostase do pool (tamanho ótimo)
    - Detectar sinais de diferenciação
    - Executar diferenciação baseada em DNA + sinal metabólico
    - Gerenciar plasticidade e especialização reversível
    - Monitorar saúde do pool
    """
    
    def __init__(self, 
                 initial_size: int = 10,
                 min_size: int = 5,
                 max_size: int = 50,
                 base_dna: str = "STEM_ROOT_DNA_v1"):
        self.pool: Dict[str, StemAgent] = {}
        self.min_size = min_size
        self.max_size = max_size
        self.target_size = initial_size
        self.base_dna = base_dna
        self.differentiation_history: List[Dict] = []
        self.signal_queue: List[DifferentiationSignal] = []
        
        # Inicializa pool com agentes stem
        self._initialize_pool(initial_size)
    
    def _initialize_pool(self, size: int):
        """Cria pool inicial de agentes stem"""
        for i in range(size):
            agent_id = f"stem_{hashlib.sha256(f'{self.base_dna}_{i}_{datetime.now()}'.encode()).hexdigest()[:12]}"
            self.pool[agent_id] = StemAgent(
                agent_id=agent_id,
                base_dna=self.base_dna,
                potential_types=list(AgentType)
            )
    
    def receive_signal(self, signal: DifferentiationSignal):
        """Recebe sinal metabólico para diferenciação"""
        self.signal_queue.append(signal)
        # Processa sinais intensos imediatamente
        if signal.intensity > 0.7:
            self._process_signals()
    
    def _process_signals(self):
        """Processa fila de sinais e trigger diferenciações"""
        if not self.signal_queue:
            return
        
        # Agrupa sinais por tipo
        signal_map: Dict[str, List[DifferentiationSignal]] = {}
        for signal in self.signal_queue:
            if signal.signal_type not in signal_map:
                signal_map[signal.signal_type] = []
            signal_map[signal.signal_type].append(signal)
        
        # Processa cada tipo de sinal
        for signal_type, signals in signal_map.items():
            avg_intensity = sum(s.intensity for s in signals) / len(signals)
            self._differentiate_by_demand(signal_type, avg_intensity, signals)
        
        self.signal_queue.clear()
    
    def _differentiate_by_demand(self, signal_type: str, intensity: float, signals: List[DifferentiationSignal]):
        """Diferencia agentes baseado na demanda do sinal"""
        
        # Mapeia tipo de sinal para tipo de agente
        type_mapping = {
            "code_urgency": AgentType.CODER,
            "analysis_need": AgentType.ANALYST,
            "exploration_request": AgentType.EXPLORER,
            "security_threat": AgentType.GUARDIAN,
            "optimization_pressure": AgentType.OPTIMIZER,
        }
        
        target_type = type_mapping.get(signal_type)
        if not target_type:
            return
        
        # Calcula quantos agentes diferenciar (baseado na intensidade)
        needed_count = max(1, int(intensity * 3))  # 1-3 agentes
        
        # Seleciona melhores candidatos (maior plasticidade, menor especialização recente)
        candidates = self._select_candidates(target_type, needed_count)
        
        for candidate_id in candidates:
            self._execute_differentiation(candidate_id, target_type, signals)
    
    def _select_candidates(self, target_type: AgentType, count: int) -> List[str]:
        """Seleciona melhores candidatos para diferenciação"""
        candidates = []
        
        for agent_id, agent in self.pool.items():
            # Só considera agentes stem ou com alta plasticidade
            if agent.current_type == AgentType.STEMMING or agent.plasticity_score > 0.7:
                if target_type in agent.potential_types:
                    # Score de seleção: plasticidade + tempo desde última diferenciação
                    time_factor = 1.0
                    if agent.last_differentiation:
                        hours_since = (datetime.now() - agent.last_differentiation).total_seconds() / 3600
                        time_factor = min(1.0, hours_since / 24)  # Normaliza até 24h
                    
                    score = agent.plasticity_score * 0.7 + time_factor * 0.3
                    candidates.append((agent_id, score))
        
        # Ordena por score e retorna top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:count]]
    
    def _execute_differentiation(self, agent_id: str, target_type: AgentType, signals: List[DifferentiationSignal]):
        """Executa diferenciação de um agente"""
        if agent_id not in self.pool:
            return
        
        agent = self.pool[agent_id]
        old_type = agent.current_type
        
        # Modifica DNA baseado no sinal (epigenética)
        new_dna = self._compute_differentiated_dna(agent.base_dna, target_type, signals)
        
        # Atualiza estado do agente
        agent.current_type = target_type
        agent.differentiation_count += 1
        agent.last_differentiation = datetime.now()
        agent.metabolic_state["last_signal"] = signals[-1].signal_type if signals else "unknown"
        agent.metabolic_state["differentiation_trigger"] = sum(s.intensity for s in signals) / len(signals) if signals else 0
        
        # Reduz plasticidade (especialização tem custo)
        agent.plasticity_score *= 0.85
        
        # Registra histórico
        self.differentiation_history.append({
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "old_type": old_type.value,
            "new_type": target_type.value,
            "dna_hash": hashlib.sha256(new_dna.encode()).hexdigest()[:16],
            "signal_count": len(signals),
            "avg_intensity": sum(s.intensity for s in signals) / len(signals) if signals else 0
        })
    
    def _compute_differentiated_dna(self, base_dna: str, target_type: AgentType, signals: List[DifferentiationSignal]) -> str:
        """Computa DNA diferenciado baseado em sinais epigenéticos"""
        # Combina DNA base com marcadores epigenéticos do tipo alvo
        signal_signature = "".join([
            f"{s.signal_type}:{s.intensity:.2f};"
            for s in signals[-3:]  # Últimos 3 sinais
        ])
        
        differentiated = f"{base_dna}|{target_type.value}|{signal_signature}|{datetime.now().timestamp()}"
        return differentiated
    
    def revert_differentiation(self, agent_id: str) -> bool:
        """Reverte agente especializado para estado stem (plasticidade)"""
        if agent_id not in self.pool:
            return False
        
        agent = self.pool[agent_id]
        
        # Só reverte se plasticidade permitir
        if agent.plasticity_score < 0.3:
            return False
        
        old_type = agent.current_type
        agent.current_type = AgentType.STEMMING
        agent.plasticity_score = min(1.0, agent.plasticity_score * 1.2)  # Recupera plasticidade
        agent.metabolic_state["reverted_from"] = old_type.value
        agent.metabolic_state["reversion_time"] = datetime.now().isoformat()
        
        return True
    
    def maintain_homeostasis(self) -> Dict[str, int]:
        """Mantém homeostase do pool (auto-renovação)"""
        stats = {
            "created": 0,
            "removed": 0,
            "current_size": len(self.pool)
        }
        
        current_size = len(self.pool)
        
        # Se abaixo do mínimo, cria novos stem agents
        if current_size < self.min_size:
            needed = self.target_size - current_size
            for _ in range(needed):
                agent_id = f"stem_{hashlib.sha256(f'{self.base_dna}_{datetime.now()}_{random.random()}'.encode()).hexdigest()[:12]}"
                self.pool[agent_id] = StemAgent(
                    agent_id=agent_id,
                    base_dna=self.base_dna,
                    potential_types=list(AgentType)
                )
                stats["created"] += 1
        
        # Se acima do máximo, remove agentes menos plásticos (exceto stems)
        elif current_size > self.max_size:
            # Ordena por plasticidade (remove menos plásticos primeiro)
            sorted_agents = sorted(
                [(aid, a) for aid, a in self.pool.items() if a.current_type != AgentType.STEMMING],
                key=lambda x: x[1].plasticity_score
            )
            
            to_remove = current_size - self.target_size
            for agent_id, _ in sorted_agents[:to_remove]:
                del self.pool[agent_id]
                stats["removed"] += 1
        
        stats["current_size"] = len(self.pool)
        return stats
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas detalhadas do pool"""
        type_counts = {}
        avg_plasticity = 0
        total_diffs = 0
        
        for agent in self.pool.values():
            type_counts[agent.current_type.value] = type_counts.get(agent.current_type.value, 0) + 1
            avg_plasticity += agent.plasticity_score
            total_diffs += agent.differentiation_count
        
        agent_count = len(self.pool)
        
        return {
            "total_agents": agent_count,
            "type_distribution": type_counts,
            "avg_plasticity": avg_plasticity / agent_count if agent_count > 0 else 0,
            "total_differentiations": total_diffs,
            "recent_differentiations": len(self.differentiation_history[-10:]),
            "pending_signals": len(self.signal_queue),
            "homeostasis_status": "healthy" if self.min_size <= agent_count <= self.max_size else "unstable"
        }
    
    def request_specialized_agent(self, agent_type: AgentType) -> Optional[StemAgent]:
        """Solicita agente especializado (trigger diferenciação se necessário)"""
        # Tenta encontrar agente já especializado
        for agent in self.pool.values():
            if agent.current_type == agent_type and agent.plasticity_score > 0.3:
                return agent
        
        # Nenhum disponível, cria sinal de demanda
        signal = DifferentiationSignal(
            signal_type=f"{agent_type.value}_request",
            intensity=0.9,
            source="pool_request"
        )
        self.receive_signal(signal)
        self._process_signals()
        
        # Tenta novamente após diferenciação
        for agent in self.pool.values():
            if agent.current_type == agent_type:
                return agent
        
        return None


# Exemplo de uso integrado
if __name__ == "__main__":
    print("🧬 Stem Agent Pool - Demonstração\n")
    
    # Cria pool
    pool = StemAgentPool(initial_size=15)
    
    print(f"Pool inicial: {pool.get_pool_stats()['total_agents']} agentes")
    print(f"Distribuição: {pool.get_pool_stats()['type_distribution']}\n")
    
    # Simula sinais de demanda
    signals = [
        DifferentiationSignal("code_urgency", 0.85, source="metabolic_sensor"),
        DifferentiationSignal("security_threat", 0.95, source="immunity_system"),
        DifferentiationSignal("analysis_need", 0.6, source="cognition_module"),
    ]
    
    for signal in signals:
        print(f"📶 Recebendo sinal: {signal.signal_type} (intensidade: {signal.intensity})")
        pool.receive_signal(signal)
    
    # Processa diferenciações
    pool._process_signals()
    
    print(f"\n📊 Após diferenciação:")
    stats = pool.get_pool_stats()
    print(f"Total: {stats['total_agents']} agentes")
    print(f"Distribuição: {stats['type_distribution']}")
    print(f"Plasticidade média: {stats['avg_plasticity']:.2f}")
    print(f"Diferenciações totais: {stats['total_differentiations']}")
    
    # Testa homeostase
    print(f"\n🔄 Mantendo homeostase...")
    homeo = pool.maintain_homeostasis()
    print(f"Criados: {homeo['created']}, Removidos: {homeo['removed']}, Tamanho atual: {homeo['current_size']}")
    
    # Solicita agente especializado
    print(f"\n🎯 Solicitando agente CODER...")
    coder = pool.request_specialized_agent(AgentType.CODER)
    if coder:
        print(f"✅ Agente encontrado: {coder.agent_id} (tipo: {coder.current_type.value})")
    
    print(f"\n📝 Histórico de diferenciações:")
    for diff in pool.differentiation_history[-3:]:
        print(f"  {diff['agent_id']}: {diff['old_type']} → {diff['new_type']}")
