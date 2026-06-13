"""RetryHandler — Retry inteligente com correção de prompt e escalonamento.

Quando o modelo falha:
1. Detecta o tipo de falha (vazio, erro, alucinação, timeout)
2. Reescreve o prompt corrigindo a abordagem
3. Escalona modelos: local → cloud → externo (ChatGPT Web)
4. Aprende qual estratégia funciona para cada tipo de erro
"""

import re
import json
import time
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from collections import Counter

from iaglobal.utils.logger import logger


@dataclass
class RetryResult:
    success: bool
    output: str
    model_used: str
    attempts: int
    error_type: str = ""
    escalation_level: int = 0  # 0=local, 1=cloud, 2=external


class PromptFixer:
    """Reescreve prompts baseado em análise de erro."""

    @staticmethod
    def fix(prompt: str, error: str, error_type: str) -> str:
        """Gera prompt corrigido com base no tipo de erro."""
        fixers = {
            "empty": PromptFixer._fix_empty,
            "error": PromptFixer._fix_error,
            "hallucination": PromptFixer._fix_hallucination,
            "timeout": PromptFixer._fix_timeout,
            "code_error": PromptFixer._fix_code_error,
        }
        fixer = fixers.get(error_type, PromptFixer._fix_generic)
        return fixer(prompt, error)

    @staticmethod
    def _fix_empty(prompt: str, error: str) -> str:
        return f"""{prompt}

[RETRY INSTRUCTION - RESPOSTA VAZIA]
A resposta anterior veio vazia. Seja direto e objetivo.
Escreva APENAS a resposta solicitada, sem explicações extensas.
Comece respondendo imediatamente."""

    @staticmethod
    def _fix_error(prompt: str, error: str) -> str:
        return f"""{prompt}

[RETRY INSTRUCTION - ERRO DE EXECUÇÃO]
Ocorreu um erro: {error[:200]}
Corrija o problema e gere uma versão que funcione corretamente.
Código deve ser executável e completo."""

    @staticmethod
    def _fix_hallucination(prompt: str, error: str) -> str:
        return f"""{prompt}

[RETRY INSTRUCTION - ALUCAÇÃO DETECTADA]
A resposta anterior continha informações inventadas.
NÃO invente dados, bibliotecas ou APIs.
Use apenas o contexto fornecido.
Se não tiver certeza, responda "UNKNOWN"."""

    @staticmethod
    def _fix_timeout(prompt: str, error: str) -> str:
        return f"""{prompt}

[RETRY INSTRUCTION - TIMEOUT]
A resposta anterior demorou muito.
Seja mais conciso. Responda em menos passos.
Priorize código direto sobre explicações longas."""

    @staticmethod
    def _fix_code_error(prompt: str, error: str) -> str:
        return f"""{prompt}

[RETRY INSTRUCTION - ERRO DE CÓDIGO]
O código gerado contém erros: {error[:200]}
Corrija os problemas específicos apontados.
Garanta que o código seja executável e semanticamente correto."""

    @staticmethod
    def _fix_generic(prompt: str, error: str) -> str:
        return f"""{prompt}

[RETRY INSTRUCTION]
Houve um problema na execução anterior: {error[:200]}
Reveja e corrija sua resposta."""


class ErrorDetector:
    """Detecta e classifica erros em saídas de LLM."""

    @staticmethod
    def detect(output: str, error: Optional[str] = None) -> str:
        """Detecta tipo de erro na saída."""
        if error and "timeout" in error.lower():
            return "timeout"
        if not output or not output.strip():
            return "empty"
        if len(output.strip()) < 5:
            return "empty"
        if "UNKNOWN" in output:
            return "unknown"  # not actually an error, intentional
        if re.search(r"Traceback|Error:|Exception|SyntaxError", output):
            return "code_error"
        # Check for hallucination indicators
        if re.search(r"(não tenho certeza|posso estar enganado|talvez|provavelmente)", output.lower()):
            return "hallucination"
        return "ok"

    @staticmethod
    def needs_retry(error_type: str) -> bool:
        """Determina se o erro merece retry."""
        return error_type in ("empty", "error", "hallucination", "timeout", "code_error")


class ModelEscalator:
    """Escalona modelos de forma balanceada: local → cloud → externo."""

    TIERS = {
        0: {  # Cloud APIs (mais rápidos, maior qualidade)
            "models": ["openrouter/poolside/laguna-m.1:free", "nvidia/mistralai/mistral-small-4-119b-2603",
                       "groq/llama-3.1-8b-instant", "gemini/gemini-2.5-flash-lite"],
            "label": "cloud",
        },
        1: {  # Web LLMs (sem login via Playwright)
            "models": ["perplexity/default", "hf_router/deepseek-ai/DeepSeek-V4-Flash"],
            "label": "web_llm",
        },
        2: {  # Local (Ollama com RAG — retaguarda)
            "models": ["ollama/qwen2.5:0.5b", "ollama/tinyllama:latest"],
            "label": "local",
        },
    }

    def __init__(self):
        self._level_success: Counter = Counter()
        self._level_attempts: Counter = Counter()

    def get_models(self, level: int) -> List[str]:
        """Retorna modelos para um nível de escalonamento."""
        tier = self.TIERS.get(level, self.TIERS[0])
        return tier["models"]

    def get_label(self, level: int) -> str:
        tier = self.TIERS.get(level, self.TIERS[0])
        return tier["label"]

    def escalate(self, current_level: int) -> Optional[int]:
        """Sobe um nível de escalonamento se disponível."""
        next_level = current_level + 1
        if next_level in self.TIERS:
            return next_level
        return None

    def record(self, level: int, success: bool):
        """Registra resultado para balanceamento futuro."""
        self._level_attempts[level] += 1
        if success:
            self._level_success[level] += 1

    def get_success_rate(self, level: int) -> float:
        attempts = self._level_attempts.get(level, 0)
        if attempts == 0:
            return 0.5
        return self._level_success.get(level, 0) / attempts

    def get_stats(self) -> Dict:
        return {
            f"level_{k}_rate": f"{self.get_success_rate(k):.2f}"
            for k in self.TIERS
        }


class RetryHandler:
    """Gerenciador de retry inteligente com correção de prompt e escalonamento."""

    def __init__(self, llm_router: Callable, max_attempts: int = 5,
                 local_first: bool = True):
        self.llm_router = llm_router
        self.max_attempts = max_attempts
        self.local_first = local_first
        self.detector = ErrorDetector()
        self.fixer = PromptFixer()
        self.escalator = ModelEscalator()
        self._history: List[Dict] = []

    def execute(self, prompt: str, model: str = "auto") -> RetryResult:
        """Executa com retry inteligente."""
        start_time = time.time()
        current_prompt = prompt
        current_level = 0 if self.local_first else 1
        attempt = 0
        last_error = ""
        used_models = []

        logger.info(f"[RETRY] Iniciando: prompt_len={len(prompt)} model={model} "
                    f"local_first={self.local_first} max_attempts={self.max_attempts}")

        while attempt < self.max_attempts:
            attempt += 1

            # Get models for current escalation level
            models = self.escalator.get_models(current_level)
            output = None
            model_used = model

            logger.debug(f"[RETRY] Attempt {attempt}/{self.max_attempts}: "
                         f"level={current_level}({self.escalator.get_label(current_level)}) "
                         f"models={[m.split('/')[-1] for m in models]}")

            for m in models:
                try:
                    output = self.llm_router(m, current_prompt)
                    model_used = m
                    used_models.append(m)
                    if output:
                        break
                except Exception as e:
                    last_error = str(e)
                    logger.debug(f"[RETRY] Model {m.split('/')[-1]} fail: {str(e)[:60]}")
                    continue

            if not output:
                last_error = "empty_or_error"
                error_type = "error"
                logger.warning(f"[RETRY] Attempt {attempt}: todos os modelos falharam (vazio/erro)")
            else:
                error_type = self.detector.detect(output, last_error)
                if error_type != "ok":
                    logger.warning(f"[RETRY] Attempt {attempt}: erro detectado={error_type} "
                                   f"output_len={len(output)} model={model_used.split('/')[-1]}")
                else:
                    logger.info(f"[RETRY] Attempt {attempt}: sucesso model={model_used.split('/')[-1]} "
                                f"output_len={len(output)} level={current_level}")

            if error_type == "ok":
                self.escalator.record(current_level, True)
                self._history.append({
                    "attempt": attempt, "level": current_level,
                    "model": model_used, "success": True, "error_type": "ok",
                })
                elapsed = time.time() - start_time
                logger.info(f"[RETRY] Concluído com sucesso: attempts={attempt} "
                            f"level={current_level} elapsed={elapsed:.2f}s")
                return RetryResult(
                    success=True, output=output,
                    model_used=model_used,
                    attempts=attempt,
                    escalation_level=current_level,
                )

            if error_type == "unknown":
                self.escalator.record(current_level, True)
                self._history.append({
                    "attempt": attempt, "level": current_level,
                    "model": model_used, "success": True, "error_type": "unknown",
                })
                elapsed = time.time() - start_time
                logger.info(f"[RETRY] UNKNOWN (intencional): attempts={attempt} elapsed={elapsed:.2f}s")
                return RetryResult(
                    success=True, output=output,
                    model_used=model_used,
                    attempts=attempt,
                    escalation_level=current_level,
                )

            # Fix prompt based on error
            self.escalator.record(current_level, False)
            current_prompt = self.fixer.fix(current_prompt, last_error or output[:200], error_type)
            last_error = f"attempt {attempt}: {error_type}"
            logger.debug(f"[RETRY] Prompt corrigido para attempt {attempt + 1}: "
                         f"error_type={error_type} new_prompt_len={len(current_prompt)}")

            # Escalate if needed
            if attempt >= 2 and current_level == 0:
                next_level = self.escalator.escalate(current_level)
                if next_level is not None:
                    logger.info(f"[RETRY] Escalando de {self.escalator.get_label(current_level)} "
                                f"para {self.escalator.get_label(next_level)} "
                                f"(após {attempt} tentativas, erro: {error_type})")
                    current_level = next_level
            elif attempt >= 4 and current_level == 1:
                next_level = self.escalator.escalate(current_level)
                if next_level is not None:
                    logger.info(f"[RETRY] Escalando para external (após {attempt} tentativas)")
                    current_level = next_level

        elapsed = time.time() - start_time
        logger.error(f"[RETRY] Esgotado após {self.max_attempts} tentativas: "
                     f"last_error={last_error} elapsed={elapsed:.2f}s")
        self._history.append({
            "attempt": attempt, "level": current_level,
            "model": model_used, "success": False, "error_type": error_type,
        })
        return RetryResult(
            success=False, output=output or "",
            model_used=used_models[-1] if used_models else "none",
            attempts=attempt, error_type=error_type,
            escalation_level=current_level,
        )

    def get_stats(self) -> Dict:
        """Estatísticas de retry."""
        total = len(self._history)
        success = sum(1 for h in self._history if h["success"])
        by_error = Counter(h.get("error_type", "?") for h in self._history)
        logger.debug(f"[RETRY] Stats: total={total} success_rate={success/total:.2f} "
                     f"errors={dict(by_error.most_common(3))}")
        return {
            "total_attempts": total,
            "success_rate": f"{success/total:.2f}" if total else "N/A",
            "by_level": self.escalator.get_stats(),
            "by_error": dict(by_error.most_common(5)),
            "history": self._history[-5:],
        }

    def get_history(self) -> List[Dict]:
        return list(self._history)
