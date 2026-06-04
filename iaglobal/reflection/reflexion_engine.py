# reflection/reflexion_engine.py
# Reflexion engine module for self-correcting code generation.
# Version: 2.0 - Refactored with class structure and robust error handling

import os
import re
import sys

from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field

# Internal imports (adjust paths as needed for your project structure)
from iaglobal.memory.memory_error import query_relevant_errors, store_error, format_errors_for_prompt
from iaglobal.execution.sandbox import executar_codigo_sandbox
from iaglobal.models.event_bus import bus, EventType
from iaglobal.memory.db_manager import db as checkpoint_db
from iaglobal.utils.logger import logger

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

MAX_PROMPT_TRUNCATE = 1000
MAX_ERROR_TRUNCATE = 1000
DEFAULT_MAX_ITERATIONS = 5
CODE_BLOCK_PATTERN = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def safe_truncate(text: str, max_len: int, suffix: str = "...") -> str:
    """Truncate text safely at word boundaries to avoid cutting important info."""
    if not text or len(text) <= max_len:
        return text or ""
    # Try to break at last space before limit
    truncated = text[:max_len - len(suffix)].rsplit(" ", 1)[0]
    return truncated + suffix if truncated else text[:max_len] + suffix


def extract_code_block(text: str) -> str:
    """
    Extract Python code from markdown blocks using regex.
    Handles ```python and ``` variations, returns raw code if no block found.
    """
    if not text:
        return ""
    
    match = CODE_BLOCK_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    
    # Fallback: return stripped text if no code block detected
    return text.strip()

# Em reflection/reflexion_engine.py
def analisar_falha(self, task_id: str, feedback: str) -> Dict:
    # 1. Busca os logs ou histórico daquela task específica
    # 2. Pede para um modelo analítico (CriticAgent) revisar o log
    # 3. Retorna um plano de correção
    pass

def format_error_type(traceback_err: str) -> str:
    """Extract error type from traceback string safely."""
    if not traceback_err:
        return "UnknownError"
    if ":" in traceback_err:
        return traceback_err.split(":")[0].strip().split()[-1]
    return traceback_err.strip().split()[0] if traceback_err.strip() else "RuntimeError"


# =============================================================================
# CORE AGENT FUNCTIONS (Stateless - for testing/mock flexibility)
# =============================================================================

def generate_solution(model_fn: Callable[[str], str], prompt: str, historical_context: str) -> str:
    """
    Generate initial code solution with error history injection for prevention.
    
    Args:
        model_fn: Callable that accepts prompt and returns model response
        prompt: Current task description
        historical_context: Formatted string of past errors to avoid
        
    Returns:
        Raw model response (may contain markdown code blocks)
    """
    full_prompt = f"""{historical_context}

Current Task:
{prompt}

Instructions:
- Write clean, production-ready Python code
- Handle edge cases and potential errors
- Provide ONLY the code inside ```python blocks
- Do not include explanations outside the code block

Your solution:"""
    
    return model_fn(full_prompt)


def analyze_and_fix(
    model_fn: Callable[[str], str], 
    prompt: str, 
    failed_code: str, 
    traceback_err: str,
    historical_context: str = ""
) -> str:
    """
    Critic/Debugger agent: Analyzes broken code with real error traceback
    and generates a corrected version.
    
    Args:
        model_fn: Model inference function
        prompt: Original task description
        failed_code: Code that failed execution
        traceback_err: Actual error message from sandbox
        historical_context: Optional context of past similar errors
        
    Returns:
        Raw model response with proposed fix
    """
    critic_prompt = f"""You are a Senior Software Engineer acting as an Auto-Debugger.
Your task is to fix code that failed during sandbox execution.

## Original Task:
{prompt}

## Failed Code:
```python
{failed_code}
```

## Execution Error:
{traceback_err}

{f'## Historical Errors to Avoid (learn from past mistakes):\n{historical_context}\n' if historical_context else ''}

## Your Mission:
1. Analyze the error traceback carefully
2. Identify the root cause (syntax, logic, import, runtime, etc.)
3. Write a corrected version that:
   - Fixes the specific error
   - Maintains the original intent
   - Adds defensive programming where appropriate
   - Is ready for production use

Provide ONLY the corrected code inside ```python blocks.
Do not include explanations, comments about the fix, or markdown outside the code block.

Corrected code:"""
    
    return model_fn(critic_prompt)


def reflexion_loop(
    model_fn: Callable[[str], str], 
    prompt: str, 
    max_iterations: int = DEFAULT_MAX_ITERATIONS
) -> str:
    """
    Main reflexion loop: Generate → Execute → Analyze → Fix → Repeat
    
    Args:
        model_fn: Model inference function
        prompt: Task description for code generation
        max_iterations: Maximum correction attempts before giving up
        
    Returns:
        Final code (successful or best effort after max iterations)
    """
    # 1. Retrieve relevant past errors for prevention
    errors_past = query_relevant_errors(prompt, limit=2)
    historical_context = format_errors_for_prompt(errors_past)

    # 2. Generate first draft
    raw_response = generate_solution(model_fn, prompt, historical_context)
    current_code = extract_code_block(raw_response)

    iteration = 1
    while iteration <= max_iterations:
        logger.info(f"🔄 Attempt {iteration}/{max_iterations} - Executing in Sandbox...")
        
        # 3. Empirical test in isolated sandbox
        result = executar_codigo_sandbox(current_code)
        
        if result.get("sucesso"):
            logger.info("✅ Code executed successfully in sandbox!")
            bus.publish(EventType.REFLECTION_COMPLETED, {
                "status": "success",
                "iterations": iteration,
                "prompt_preview": safe_truncate(prompt, MAX_PROMPT_TRUNCATE)
            }, source="reflexion_engine.reflexion_loop")
            return current_code
            
        # 4. Handle failure: activate reflexion with REAL error data
        traceback_err = result.get("output", "Unknown runtime error - no output captured")
        logger.warning(f"❌ Failure on attempt {iteration}. Activating reflexion engine.")
        logger.debug(f"Error details: {safe_truncate(traceback_err, 500)}")
        
        bus.publish(EventType.EXECUTION_FAILED, {
            "iteration": iteration,
            "error_type": format_error_type(traceback_err),
            "error_preview": safe_truncate(traceback_err, MAX_ERROR_TRUNCATE),
            "prompt_preview": safe_truncate(prompt, MAX_PROMPT_TRUNCATE)
        }, source="reflexion_engine.reflexion_loop")
        
        # 5. Debugger agent attempts fix based on actual traceback
        raw_fixed_response = analyze_and_fix(
            model_fn, prompt, current_code, traceback_err, historical_context
        )
        corrected_code = extract_code_block(raw_fixed_response)
        
        # 6. Persist failure + correction to memory for future prevention
        store_error(
            prompt=prompt,
            response=current_code,
            critique=traceback_err,
            corrected=corrected_code,
            error_type=format_error_type(traceback_err)
        )
        
        bus.publish(EventType.MEMORY_SAVED, {
            "memory_type": "error_correction",
            "error_type": format_error_type(traceback_err),
            "prompt_preview": safe_truncate(prompt, MAX_PROMPT_TRUNCATE),
            "iteration": iteration
        }, source="reflexion_engine.reflexion_loop")
        
        # Prepare for next iteration
        current_code = corrected_code
        iteration += 1

    # Max iterations reached without success
    logger.error(f"💥 Reached maximum iterations ({max_iterations}) without successful execution.")
    bus.publish(EventType.REFLECTION_COMPLETED, {
        "status": "failed",
        "iterations": max_iterations,
        "prompt_preview": safe_truncate(prompt, MAX_PROMPT_TRUNCATE),
        "final_error": safe_truncate(traceback_err, MAX_ERROR_TRUNCATE)
    }, source="reflexion_engine.reflexion_loop")
    
    return f"# ⚠️ Failed to auto-correct after {max_iterations} attempts.\n# Last error: {safe_truncate(traceback_err, 150)}\n# Final code version below:\n\n{current_code}"


# =============================================================================
# REFLEXION ENGINE CLASS (Stateful orchestrator)
# =============================================================================

@dataclass
class ExecutionRecord:
    """Structured record of a single reflexion execution."""
    prompt: str
    code: str
    status: str  # "success", "failed", "error", "timeout"
    output: str
    iterations: int = 0
    error_type: Optional[str] = None
    timestamp: Optional[float] = field(default_factory=lambda: None)


class ReflexionEngine:
    """
    Stateful engine for self-correcting code generation via reflexion loop.
    
    Features:
    - Iterative code generation with sandbox validation
    - Error memory for preventing repeated mistakes
    - Event bus integration for observability
    - Batch processing and statistics tracking
    """
    
    def __init__(
        self, 
        model_fn: Callable[[str], str], 
        max_iterations: int = DEFAULT_MAX_ITERATIONS
    ):
        """
        Initialize the ReflexionEngine.
        
        Args:
            model_fn: Callable that accepts a prompt string and returns model response
            max_iterations: Max correction attempts per task (default: 3)
        """
        self.model_fn = model_fn
        self.max_iterations = max_iterations
        self.execution_history: List[ExecutionRecord] = []
        self.error_corrections: List[Dict[str, Any]] = []
        self.success_count: int = 0
        self.failure_count: int = 0
        
        logger.info(f"🔧 ReflexionEngine initialized with max_iterations={max_iterations}")

    def reflect(self, prompt: str, execution_id: Optional[str] = None, node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute reflexion loop for a single prompt and return structured result.

        Se execution_id e node_id forem fornecidos, integra com o sistema
        de checkpoint: reseta o nó falho para PENDING e permite re-execução.
        
        Args:
            prompt: Task description for code generation
            execution_id: ID da execução para checkpoint
            node_id: ID do nó que falhou
            
        Returns:
            Dictionary with execution results (code, status, output, metadata)
        """
        import time
        start_time = time.time()
        
        try:
            # Se temos checkpoint, reseta o nó falho antes de tentar novamente
            if execution_id and node_id:
                logger.info(f"🔄 Reflexion resetando checkpoint: {execution_id}/{node_id}")
                checkpoint_db.reset_failed_node(execution_id, node_id)

            # Execute main reflexion loop
            code = reflexion_loop(self.model_fn, prompt, self.max_iterations)
            
            # Final validation of returned code
            result = executar_codigo_sandbox(code)
            elapsed = time.time() - start_time
            
            if result.get("sucesso"):
                self.success_count += 1
                status = "success"
                logger.info(f"✨ Reflexion completed successfully in {elapsed:.2f}s")
            else:
                self.failure_count += 1
                status = "failed"
                logger.warning(f"⚠️ Final validation failed after reflexion loop")
            
            # Create structured record
            record = ExecutionRecord(
                prompt=prompt,
                code=code,
                status=status,
                output=result.get("output", ""),
                iterations=self.max_iterations,  # Could track actual iterations if needed
                error_type=format_error_type(result.get("output", "")) if not result.get("sucesso") else None,
                timestamp=start_time
            )
            
            self.execution_history.append(record)
            
            # Return dict for backward compatibility
            return {
                'prompt': prompt,
                'code': code,
                'status': status,
                'output': result.get("output", ""),
                'iterations': record.iterations,
                'elapsed_seconds': round(elapsed, 2)
            }
            
        except TimeoutError as e:
            logger.error(f"⏱️ Timeout during reflexion: {e}")
            self.failure_count += 1
            return {
                'prompt': prompt,
                'code': '',
                'status': 'timeout',
                'output': f'TimeoutError: {str(e)}',
                'error_type': 'TimeoutError'
            }
            
        except MemoryError as e:
            logger.error(f"💾 Memory error during reflexion: {e}")
            self.failure_count += 1
            return {
                'prompt': prompt,
                'code': '',
                'status': 'memory_error',
                'output': f'MemoryError: {str(e)}',
                'error_type': 'MemoryError'
            }
            
        except Exception as e:
            logger.exception(f"💥 Unexpected error in reflexion loop: {e}")
            self.failure_count += 1
            return {
                'prompt': prompt,
                'code': '',
                'status': 'error',
                'output': f'{type(e).__name__}: {str(e)}',
                'error_type': type(e).__name__
            }

    def batch_reflect(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """
        Execute reflexion on multiple prompts sequentially.
        
        Args:
            prompts: List of task descriptions
            
        Returns:
            List of result dictionaries in same order as input
        """
        logger.info(f"📦 Starting batch reflexion for {len(prompts)} prompts")
        results = []
        
        for idx, prompt in enumerate(prompts, 1):
            logger.info(f"🔄 Processing prompt {idx}/{len(prompts)}")
            result = self.reflect(prompt)
            results.append(result)
            
            # Optional: Add small delay to avoid rate limiting
            # time.sleep(0.1)
            
        logger.info(f"✅ Batch completed: {self.success_count}/{len(prompts)} successes")
        return results

    def get_success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100) if total > 0 else 0.0

    def get_statistics(self) -> Dict[str, Any]:
        """Return comprehensive execution statistics."""
        return {
            'total_executions': len(self.execution_history),
            'successes': self.success_count,
            'failures': self.failure_count,
            'success_rate_percent': round(self.get_success_rate(), 2),
            'corrections_stored': len(self.error_corrections),
            'current_max_iterations': self.max_iterations
        }

    def get_execution_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get execution history as list of dictionaries.
        
        Args:
            limit: Optional max number of recent records to return
            
        Returns:
            List of execution records (most recent last)
        """
        history = [
            {
                'prompt': rec.prompt,
                'code': rec.code,
                'status': rec.status,
                'output': rec.output,
                'iterations': rec.iterations,
                'error_type': rec.error_type,
                'timestamp': rec.timestamp
            }
            for rec in self.execution_history
        ]
        return history[-limit:] if limit else history.copy()

    def get_recent_failures(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most recent failed executions for analysis."""
        return [
            rec for rec in self.get_execution_history()
            if rec['status'] in ('failed', 'error', 'timeout')
        ][-limit:]

    def clear_history(self) -> None:
        """Reset all execution history and counters."""
        self.execution_history = []
        self.error_corrections = []
        self.success_count = 0
        self.failure_count = 0
        logger.info("🧹 Execution history cleared")

    def set_max_iterations(self, max_iterations: int) -> None:
        """Update maximum iterations for future reflexion loops."""
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        self.max_iterations = max_iterations
        logger.info(f"🔧 Updated max_iterations to {max_iterations}")

    def set_model(self, model_fn: Callable[[str], str]) -> None:
        """Replace the model inference function."""
        if not callable(model_fn):
            raise TypeError("model_fn must be a callable")
        self.model_fn = model_fn
        logger.info("🔄 Model function updated")

    def export_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report for monitoring/auditing."""
        return {
            'engine_config': {
                'max_iterations': self.max_iterations,
                'model_fn': repr(self.model_fn)
            },
            'statistics': self.get_statistics(),
            'recent_executions': self.get_execution_history(limit=10),
            'recent_failures': self.get_recent_failures(limit=5)
        }

