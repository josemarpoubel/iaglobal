# iaglobal/evolution/evolutionruntime.py

import asyncio
import time
import traceback
from typing import Optional, Dict, Any
from iaglobal.utils.logger import logger

# ==============================================================================
# 🏗️ MOTOR CORE: EVOLUTION RUNTIME FLEXÍVEL
# ==============================================================================

import asyncio
import logging
from typing import Optional, Dict, Any

# Definimos a variável global no topo do módulo
_runtime_instance: Optional['EvolutionRuntime'] = None


def get_runtime() -> 'EvolutionRuntime':
    """Retorna a instância Singleton do EvolutionRuntime, criando se necessário."""
    global _runtime_instance
    if _runtime_instance is None:
        _runtime_instance = EvolutionRuntime()
    return _runtime_instance

class EvolutionRuntime:
    """
    Motor de ciclo de vida 100% assíncrono, não-bloqueante e flexível.
    """

    def __new__(cls, *args, **kwargs):
        global _runtime_instance
        if _runtime_instance is None:
            _runtime_instance = super().__new__(cls)
            # Inicializamos o estado aqui para garantir que o Singleton 
            # não re-inicialize o __init__ de forma inesperada
            _runtime_instance._initialized = False 
        return _runtime_instance

    def __init__(self, evolver=None, interval: int = 60):
        # Proteção contra re-inicialização do Singleton
        if getattr(self, "_initialized", False):
            return
        
        self.evolver = evolver
        self.interval = max(5, interval)
        self.base_interval = self.interval
        
        # Estratégias e estados

        self.current_strategy = FastEvolutionStrategy()
        self.interval = self.current_strategy.interval
        
        self.cycles = 0
        self.failures = 0
        self._consecutive_stable = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._initialized = True
        logging.getLogger("iaglobal.evolution").info("🚀 EvolutionRuntime inicializado.")

    def set_strategy(self, strategy) -> None:
        """Altera a estratégia de evolução em tempo de execução."""
        self.current_strategy = strategy
        self.interval = strategy.interval
        logger.info(f"[RUNTIME] Estratégia alterada para {strategy.__class__.__name__} (intervalo={strategy.interval}s)")

    def status(self) -> Dict[str, Any]:
        """Retorna métricas em tempo real do runtime."""
        return {
            "cycles": self.cycles,
            "failures": self.failures,
            "interval": self.interval,
            "strategy": self.current_strategy.__class__.__name__,
            "running": self._running,
        }

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Inicia o loop evolutivo em background de forma não-bloqueante."""
        if self._running:
            return
        self._running = True
        current_loop = loop or asyncio.get_running_loop()
        self._task = current_loop.create_task(self._async_loop())
        logger.info("🚀 [RUNTIME] Motor Assíncrono Flexível ativado.")

    def stop(self):
        """Para o runtime imediatamente."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _async_loop(self):
        """O Loop agora é limpo, puramente assíncrono e agnóstico de estratégia."""
        try:
            while self._running:
                started_at = time.time()
                self.cycles += 1
                
                try:
                    # 🔥 TOTALMENTE ASSÍNCRONO: 
                    # Não precisamos mais de threads (asyncio.to_thread) porque o evolve_async 
                    # agora usa await nativo para chamadas de banco de dados e APIs!
                    result = await self.evolver.evolve_async(strategy=self.current_strategy)
                    
                    self.failures = 0
                    self._consecutive_stable += 1
                    
                    strategy_name = self.current_strategy.name
                    mut_count = result.get('mutations_count', 0) if isinstance(result, dict) else 0
                    logger.info(f"[CICLO #{self.cycles}] Sucesso via {strategy_name}. Mutações: {mut_count}")

                    # Backoff dinâmico descendente se estiver estável
                    if self._consecutive_stable >= 3:
                        self.interval = max(self.base_interval, int(self.interval * 0.8))

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.failures += 1
                    self._consecutive_stable = 0
                    logger.error(f"[RUNTIME-ERROR] Falha no ciclo #{self.cycles}: {e}")
                    
                    # Backoff ascendente em caso de falha (Rate limit, rede caindo)
                    self.interval = min(300, int(self.interval * 1.5))

                finally:
                    # Executa rotina de expurgo de arquivos mortos
                    await self._clean_workdirs()

                    elapsed = time.time() - started_at
                    sleep_time = max(1.0, float(self.interval) - elapsed)
                    
                    try:
                        await asyncio.sleep(sleep_time)
                    except asyncio.CancelledError:
                        break
        finally:
            self._running = False
            logger.info("🛑 [RUNTIME] Motor Assíncrono Flexível desligado.")

    async def _clean_workdirs(self):
        """Limpeza de disco assíncrona."""
        from iaglobal._paths import WORK_DIR
        try:
            def _clean():
                if WORK_DIR.exists():
                    __import__("subprocess").run(
                        ["find", str(WORK_DIR), "-mindepth", "1", "-delete"],
                        capture_output=True,
                        timeout=10,
                    )

            await asyncio.to_thread(_clean)
        except Exception:
            pass


class EvolutionStrategy:
    """Classe base para estratégias de evolução."""

    name: str = "base"
    mutation_rate: float = 0.1
    crossover_rate: float = 0.3
    selection_pressure: float = 0.5
    interval: int = 60
    exploration_rate: float = 0.2
    description: str = "Estratégia base"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "mutation_rate": self.mutation_rate,
            "crossover_rate": self.crossover_rate,
            "selection_pressure": self.selection_pressure,
            "interval": self.interval,
            "exploration_rate": self.exploration_rate,
            "description": self.description,
        }


class FastEvolutionStrategy(EvolutionStrategy):
    """
    Estratégia rápida: ciclos curtos (30s), mutações agressivas (30%),
    alta pressão seletiva (top 30% sobrevivem), alta exploração (40%).
    Ideal para descoberta inicial de variantes.
    """
    name = "fast"
    mutation_rate = 0.3
    crossover_rate = 0.5
    selection_pressure = 0.3
    interval = 30
    exploration_rate = 0.4
    description = "Ciclos curtos, mutações agressivas, alta frequência."


class DeepEvolutionStrategy(EvolutionStrategy):
    """
    Estratégia profunda: ciclos longos (120s), mutações cirúrgicas (5%),
    baixa pressão seletiva (top 70% sobrevivem), baixa exploração (5%).
    Ideal para refinamento e estabilização.
    """
    name = "deep"
    mutation_rate = 0.05
    crossover_rate = 0.1
    selection_pressure = 0.7
    interval = 120
    exploration_rate = 0.05
    description = "Ciclos longos, mutações cirúrgicas, baixa frequência."
