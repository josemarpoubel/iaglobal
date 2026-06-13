# iaglobal/evolution/evolutionruntime.py

import asyncio
import time
import traceback
from typing import Optional, Protocol, Dict, Any, List
from abc import ABC, abstractmethod
from iaglobal.utils.logger import logger

# ==============================================================================
# 🎯 SKILLS FLEXÍVEIS: INTERFACE DE ESTRATÉGIA DE EVOLUÇÃO (Strategy Pattern)
# ==============================================================================
class EvolutionStrategy(ABC):
    """Interface abstrata para definir estratégias flexíveis de evolução."""
    
    @abstractmethod
    async def execute_evolution(self, registry: Any, context: Any) -> Dict[str, Any]:
        """Executa o ciclo evolutivo de forma 100% assíncrona."""
        pass


class FastEvolutionStrategy(EvolutionStrategy):
    """Estratégia Focada em Velocidade: Muta apenas os nós críticos que falharam."""
    async def execute_evolution(self, registry: Any, context: Any) -> Dict[str, Any]:
        logger.info("[STRATEGY] Ejecutando evolução rápida assíncrona...")
        # Aqui dispararíamos tasks assíncronas concorrentes via asyncio.gather()
        await asyncio.sleep(0.5)  # Simulação de I/O de rede leve
        return {"mutations_count": 1, "strategy": "fast"}


class DeepEvolutionStrategy(EvolutionStrategy):
    """Estratégia Focada em Qualidade: Realiza Crossover e Fine-Tuning massivo."""
    async def execute_evolution(self, registry: Any, context: Any) -> Dict[str, Any]:
        logger.info("[STRATEGY] Executando evolução profunda e massiva...")
        # Simula processamento pesado e concorrência de múltiplas LLMs paralelas
        await asyncio.sleep(2.0) 
        return {"mutations_count": 5, "strategy": "deep"}

# ==============================================================================
# 🚀 PROTOCOLO ASYNC EVOLVER
# ==============================================================================
class AsyncEvolver(Protocol):
    """O Evolver agora fala a língua nativa do Asyncio."""
    async def evolve_async(self, strategy: EvolutionStrategy) -> Dict[str, Any]:
        ...

# ==============================================================================
# 🏗️ MOTOR CORE: EVOLUTION RUNTIME FLEXÍVEL
# ==============================================================================

import asyncio
import logging
from typing import Optional

# Definimos a variável global no topo do módulo
_runtime_instance: Optional['EvolutionRuntime'] = None

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
        
        self.cycles = 0
        self.failures = 0
        self._consecutive_stable = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._initialized = True
        logging.getLogger("iaglobal.evolution").info("🚀 EvolutionRuntime inicializado.")

# Função de acesso recomendada para evitar erros de escopo
def get_runtime(evolver=None, interval=60) -> 'EvolutionRuntime':
    global _runtime_instance
    if _runtime_instance is None:
        _runtime_instance = EvolutionRuntime(evolver, interval)
    return _runtime_instance

    def set_strategy(self, strategy: EvolutionStrategy):
        """Altera dinamicamente a estratégia de evolução sem derrubar o servidor."""
        logger.info(f"🔄 [RUNTIME] Alterando estratégia de evolução para: {strategy.__class__.__name__}")
        self.current_strategy = strategy

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
                    
                    # Log dinâmico baseado no retorno da estratégia flexível
                    logger.info(f"[CICLO #{self.cycles}] Sucesso via {result.get('strategy')}. Mutações: {result.get('mutations_count')}")

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
            if WORK_DIR.exists():
                await asyncio.to_thread(
                    lambda: __import__("subprocess").run(
                        ["find", str(WORK_DIR), "-mindepth", "1", "-delete"],
                        capture_output=True, timeout=10
                    )
                )
        except Exception:
            pass
