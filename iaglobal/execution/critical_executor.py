# iaglobal/execution/critical_executor.py

"""Critical executor module for error handling and critical operations."""

from typing import Tuple, Dict, Any, Optional
from iaglobal.execution.executor import executar
from iaglobal.memory.memory_storage import store_success
from iaglobal.utils.logger import logger
from iaglobal.providers.provider_config import ProviderConfig

def criticar(resposta: str, prompt: str) -> str:
    """Generate a critique prompt for the response."""
    return f"""
You are a senior software engineer.
Evaluate this response.

QUESTION:
{prompt}

RESPONSE:
{resposta}

1. What is wrong?
2. What is incomplete?
3. How should it be corrected?
Answer objectively.
"""

def store_error(prompt: str, resposta: str, critica: str, metadata: Optional[Dict] = None) -> None:
    """Store error as learning feedback."""
    try:
        error_record = f"PROMPT: {prompt}\nRESPONSE: {resposta}\nCRITIQUE: {critica}"
        store_success(prompt, resposta, metadata or {})
    except Exception as e:
        logger.error(f"Error storing feedback: {e}")

async def processar(prompt: str) -> Tuple[str, str]:
    """Process prompt with critique feedback."""
    from iaglobal.providers.provider_router import escolher_modelo
    modelo = escolher_modelo(prompt)
    resposta = await executar(modelo, {"task": prompt})
    
    critica_prompt = criticar(resposta, prompt)
    critica = await executar("nvidia", {"task": critica_prompt})
    
    store_error(prompt, resposta, critica, None)
    
    return resposta, critica

class CriticalExecutor:
    """Executor for critical operations with built-in critique and fallback."""
    
    def __init__(self, primary_provider: str = "nvidia"):
        self.primary_provider = primary_provider
        self.execution_log = []
        self.critiques = []
    
    async def execute_with_critique(self, prompt: str) -> Dict[str, Any]:
        """Execute with automatic critique."""
        # Get response
        response = await executar(self.primary_provider, {"task": prompt})
        
        # Generate critique
        critique_prompt = criticar(response, prompt)
        critique = await executar("nvidia", {"task": critique_prompt})
        
        # Store learning
        store_error(prompt, response, critique)
        
        result = {
            'prompt': prompt,
            'response': response,
            'critique': critique,
            'provider': self.primary_provider
        }
        
        self.execution_log.append(result)
        self.critiques.append(critique)
        
        return result
    
    async def execute_safe(self, prompt: str, fallback_provider: str = "ollama") -> str:
        """Execute with fallback on failure."""
        try:
            return await executar(self.primary_provider, {"task": prompt})
        except Exception as e:
            logger.warning(f"Primary provider failed: {e}. Using fallback: {fallback_provider}")
            try:
                return await executar(fallback_provider, {"task": prompt})
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                raise
    
    async def batch_execute_with_critique(self, prompts: list) -> list:
        """Execute multiple prompts with critique."""
        results = []
        for prompt in prompts:
            results.append(await self.execute_with_critique(prompt))
        return results
    
    def get_execution_log(self) -> list:
        """Get execution log."""
        return self.execution_log
    
    def get_critiques(self) -> list:
        """Get all critiques."""
        return self.critiques
    
    def clear_log(self) -> None:
        """Clear execution log."""
        self.execution_log = []
        self.critiques = []
    
    def analyze_failures(self) -> Dict[str, Any]:
        """Analyze failure patterns from critiques."""
        return {
            'total_executions': len(self.execution_log),
            'total_critiques': len(self.critiques),
            'critiques_summary': self.critiques[:10]  # Last 10 critiques
        }
