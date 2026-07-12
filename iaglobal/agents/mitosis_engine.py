# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
#!/usr/bin/env python3
"""
AgentMitosisEngine — Geração 2.5: Diferenciação Celular Computacional

Inspirado na mitose biológica, este engine:
1. Detecta padrões de task_type automaticamente
2. Diferencia agents por especialidade
3. Cria memória epigenética (configuração sem mudar DNA)
4. Implementa pool de especialistas

Ciclo Metabólico:
  AGENTE STEM → SINAL DE DIFERENCIAÇÃO → EXPRESSÃO GÊNICA → ESPECIALISTA
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import Counter, defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

from iaglobal.utils.logger import get_logger
logger = get_logger("iaglobal.agents.mitosis_engine")


@dataclass
class AgentSpecialization:
    """Representa a especialização de um agent."""
    agent_id: str
    specialization: str
    parent_agent: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_ivm: float = 0.0
    epigenetic_config: Dict = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0
    
    @property
    def fitness_score(self) -> float:
        """Calcula fitness baseado em sucesso + IVM."""
        return (self.success_rate * 0.6) + (self.avg_ivm * 0.4)


class AgentMitosisEngine:
    """
    Motor de mitose e diferenciação de agents.
    
    Analogia biológica:
    - Célula stem → Agent base (ex: coder)
    - Sinal de diferenciação →(task_type + performance)
    - Expressão gênica seletiva → Configuração epigenética
    - Célula especializada → Agent especializado (ex: python_coder)
    """
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("iaglobal/memory/mitosis_engine.json")
        
        #=Mapeamento de especializações
        self.specializations: Dict[str, AgentSpecialization] = {}
        
        # Padrões detectados: task_type → {agent_id → count}
        self.task_patterns: Dict[str, Counter] = defaultdict(Counter)
        
        # Memória epigenética: agent_id → config dinâmica
        self.epigenetic_memory: Dict[str, Dict] = {}
        
        # Agents stem disponíveis para diferenciação
        self.stem_agents: Set[str] = {
            "coder", "architect", "tester", "researcher",
            "auditor", "optimizer", "security", "documenter"
        }
        
        # Carrega estado existente
        self._load_state()
        
        logger.info(f"🧬 [MITOSE] Engine initialized | stem_agents={len(self.stem_agents)}")
    
    async def analyze_task(self, 
                          task_type: str, 
                          agent_id: str, 
                          performance_score: float,
                          ivm: float = 0.5,
                          context: Dict = None):
        """
        Analisa uma tarefa e atualiza padrões para diferenciação.
        
        Este método aprende quais agents performam melhor em cada task_type.
        """
        # Registra padrão
        self.task_patterns[task_type][agent_id] += 1
        
        # Se performance for boa, considera especialização
        if performance_score >= 0.75:
            if agent_id not in self.specializations:
                # Cria nova especialização
                spec = AgentSpecialization(
                    agent_id=agent_id,
                    specialization=task_type,
                    parent_agent=agent_id,  # Por enquanto, parent é ele mesmo
                    tasks_completed=1,
                    tasks_failed=0,
                    avg_ivm=ivm,
                    epigenetic_config=self._generate_epigenetic_config(task_type, ivm)
                )
                self.specializations[agent_id] = spec
                self.epigenetic_memory[agent_id] = spec.epigenetic_config
                
                logger.info(
                    f"🧬 [MITOSE] Nova especialização detectada: "
                    f"{agent_id} → {task_type} (IVM={ivm:.3f})"
                )
            else:
                # Atualiza especialização existente
                spec = self.specializations[agent_id]
                spec.tasks_completed += 1
                # Média móvel do IVM
                spec.avg_ivm = (spec.avg_ivm * (spec.tasks_completed - 1) + ivm) / spec.tasks_completed
                spec.epigenetic_config = self._generate_epigenetic_config(task_type, spec.avg_ivm)
                self.epigenetic_memory[agent_id] = spec.epigenetic_config
                
                logger.debug(
                    f"🧬 [MITOSE] Especialização reforçada: "
                    f"{agent_id} em {task_type} (tasks={spec.tasks_completed}, IVM={spec.avg_ivm:.3f})"
                )
        
        # Salva estado
        await self._save_state()
    
    def suggest_specialization(self, agent_id: str, available_types: List[str]) -> Optional[str]:
        """
        Sugere especialização para um agent baseado em padrões históricos.
        
        Retorna o task_type onde o agent teve melhor desempenho.
        """
        if agent_id in self.specializations:
            # Já é especializado
            return self.specializations[agent_id].specialization
        
        # Analisa histórico de padrões
        best_type = None
        best_count = 0
        
        for task_type in available_types:
            if task_type in self.task_patterns:
                count = self.task_patterns[task_type].get(agent_id, 0)
                if count > best_count:
                    best_count = count
                    best_type = task_type
        
        # Mínimo de 3 tarefas bem-sucedidas para sugerir
        if best_type and best_count >= 3:
            logger.info(f"🧬 [MITOSE] Sugerindo especialização {best_type} para {agent_id}")
            return best_type
        
        return None
    
    async def create_specialist(self, 
                               base_agent_id: str, 
                               specialization: str,
                               specialist_id: str = None) -> str:
        """
        Cria um novo agent especialista via mitose.
        
        Analogia: Célula stem se divide → uma filha mantém stem, outra diferencia.
        """
        if specialist_id is None:
            specialist_id = f"{base_agent_id}_{specialization}"
        
        # Verifica se já existe
        if specialist_id in self.specializations:
            logger.debug(f"🧬 [MITOSE] Especialista {specialist_id} já existe")
            return specialist_id
        
        # Gera configuração epigenética
        epigenetic_config = self._generate_epigenetic_config(specialization, ivm=0.8)
        
        # Cria especialização
        spec = AgentSpecialization(
            agent_id=specialist_id,
            specialization=specialization,
            parent_agent=base_agent_id,
            tasks_completed=0,
            tasks_failed=0,
            avg_ivm=0.8,  # IVM inicial otimista
            epigenetic_config=epigenetic_config
        )
        
        self.specializations[specialist_id] = spec
        self.epigenetic_memory[specialist_id] = epigenetic_config
        
        logger.info(
            f"🧬 [MITOSE] Especialista criado: {specialist_id} "
            f"(parent: {base_agent_id}, spec: {specialization})"
        )
        
        await self._save_state()
        return specialist_id
    
    def get_specialist_pool(self, task_type: str) -> List[str]:
        """
        Retorna lista de agents especializados no task_type.
        
        Ordem: por fitness_score (melhor primeiro).
        """
        specialists = []
        for spec in self.specializations.values():
            if spec.specialization == task_type or spec.specialization.startswith(task_type[:3]):
                specialists.append(spec)
        
        # Ordena por fitness
        specialists.sort(key=lambda s: s.fitness_score, reverse=True)
        
        return [s.agent_id for s in specialists]
    
    def get_epigenetic_config(self, agent_id: str) -> Dict:
        """
        Retorna configuração epigenética de um agent.
        
        Configuração epigenética = comportamento sem mudar código.
        """
        return self.epigenetic_memory.get(agent_id, self._default_config())
    
    def _generate_epigenetic_config(self, task_type: str, ivm: float) -> Dict:
        """
        Gera configuração epigenética baseada no task_type e IVM.
        
        Analogia: Metilação de histonas ativa/desativa genes.
        """
        # Configurações por tipo de tarefa
        configs = {
            "coder": {
                "temperature": 0.3 if ivm > 0.8 else 0.5,  # Mais determinístico se bom
                "max_tokens": 4096,
                "priority": "high",
                "retry_on_fail": True,
            },
            "architect": {
                "temperature": 0.2,  # Muito determinístico
                "max_tokens": 8192,
                "priority": "critical",
                "require_validation": True,
            },
            "tester": {
                "temperature": 0.1,  # Extremamente determinístico
                "max_tokens": 2048,
                "priority": "high",
                "strict_mode": True,
            },
            "researcher": {
                "temperature": 0.7,  # Mais criativo
                "max_tokens": 4096,
                "priority": "normal",
                "explore_more": True,
            },
            "security": {
                "temperature": 0.1,  # Ultra conservador
                "max_tokens": 4096,
                "priority": "critical",
                "paranoid_mode": True,
            },
        }
        
        # Retorna config específica ou default
        base_config = configs.get(task_type, self._default_config())
        
        # Ajusta baseado no IVM
        if ivm > 0.9:
            base_config["priority"] = "elite"
        elif ivm > 0.7:
            base_config["priority"] = "high"
        
        return base_config
    
    def _default_config(self) -> Dict:
        """Configuração padrão para agents sem especialização."""
        return {
            "temperature": 0.5,
            "max_tokens": 2048,
            "priority": "normal",
        }
    
    async def _save_state(self):
        """Persiste estado em disco."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "specializations": {k: asdict(v) for k, v in self.specializations.items()},
            "task_patterns": {k: dict(v) for k, v in self.task_patterns.items()},
            "epigenetic_memory": self.epigenetic_memory,
            "stem_agents": list(self.stem_agents),
        }
        
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"🧬 [MITOSE] Estado persistido: {len(self.specializations)} especializações")
    
    def _load_state(self):
        """Carrega estado de disco."""
        if not self.db_path.exists():
            logger.info("🧬 [MITOSE] Nenhum estado anterior encontrado")
            return
        
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            # Restaura especializações
            for agent_id, spec_data in state.get("specializations", {}).items():
                self.specializations[agent_id] = AgentSpecialization(**spec_data)
            
            # Restaura padrões
            for task_type, patterns in state.get("task_patterns", {}).items():
                self.task_patterns[task_type] = Counter(patterns)
            
            # Restaura memória epigenética
            self.epigenetic_memory = state.get("epigenetic_memory", {})
            
            # Restaura stem agents
            self.stem_agents = set(state.get("stem_agents", self.stem_agents))
            
            logger.info(
                f"🧬 [MITOSE] Estado carregado: "
                f"{len(self.specializations)} especializações, "
                f"{len(self.task_patterns)} task_types"
            )
        
        except Exception as e:
            logger.error(f"🧬 [MITOSE] Erro ao carregar estado: {e}")


# Singleton
_mitosis_engine_instance: Optional[AgentMitosisEngine] = None

def get_mitosis_engine() -> AgentMitosisEngine:
    """Retorna singleton do AgentMitosisEngine."""
    global _mitosis_engine_instance
    if _mitosis_engine_instance is None:
        _mitosis_engine_instance = AgentMitosisEngine()
    return _mitosis_engine_instance
