# iaglobal/execution/executor.py

"""
Autonomous AI Executor + Real Python Sandbox Runtime (REFATORADO)

- Corrige inconsistências de providers
- Remove dependências globais inexistentes
- Centraliza configuração via ProviderConfig
- Torna o router previsível e estável
- Evita loops de failover quebrados
"""

import os
import time
import json
import tempfile
import traceback
import subprocess
import requests
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List

from iaglobal.utils.logger import logger
from iaglobal.memory import cache
from iaglobal.validation.engine import ValidationEngine
from iaglobal.providers.provider_config import ProviderConfig


# =========================================================
# RESULT MODEL
# =========================================================

@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    traceback: str
    return_code: int
    execution_time: float
    attempt: int = 0
    validated_ast: bool = False


# =========================================================
# UTIL
# =========================================================

def limpar_markdown(texto: str) -> str:
    if not texto:
        return ""
    texto = texto.strip()
    if "```" in texto:
        partes = texto.split("```")
        if len(parts := partes) >= 3:
            return parts[1].strip()
    return texto


def validar_sintaxe(codigo: str) -> Optional[str]:
    try:
        engine = ValidationEngine()
        result = engine.validate(codigo)
        return None if result.valid else str(result.errors)
    except Exception as e:
        logger.error(f"AST error: {e}")
        return str(e)


# =========================================================
# PROVIDER HELPERS
# =========================================================

def _ollama_request(prompt: str, model: str = None) -> str:
    url = ProviderConfig.OLLAMA_URL.rstrip("/") + "/api/generate"
    model_name = model or ProviderConfig.DEFAULT_OLLAMA_MODEL
    # Sanitiza: se o nome contiver "/" (ex: "gemini/xxx", "openrouter/xxx"),
    # cai para o modelo padrão pois não é um modelo Ollama válido
    if "/" in model_name:
        model_name = ProviderConfig.DEFAULT_OLLAMA_MODEL

    r = requests.post(
        url,
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False
        },
        timeout=600
    )
    r.raise_for_status()
    return r.json().get("response", "")

from typing import Optional
import requests

def _groq_request(prompt: str) -> Optional[str]:
    if not ProviderConfig.GROQ_API_KEY:
        logger.debug("[Groq] API key ausente, pulando provider")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": ProviderConfig.DEFAULT_GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {ProviderConfig.GROQ_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )

        # erro HTTP detalhado (evita fallback silencioso)
        if response.status_code != 200:
            logger.warning(
                f"[Groq] HTTP {response.status_code} | {response.text[:300]}"
            )
            return None

        data = response.json()

        # parsing seguro (evita KeyError)
        try:
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            ) or None

        except Exception:
            logger.warning(f"[Groq] Resposta inesperada: {data}")
            return None

    except requests.exceptions.Timeout:
        logger.warning("[Groq] Timeout na requisição (60s)")
        return None

    except requests.exceptions.ConnectionError:
        logger.warning("[Groq] Falha de conexão com API")
        return None

    except Exception as e:
        logger.exception(f"[Groq] Erro inesperado: {str(e)}")
        return None

def _openrouter_request(prompt: str) -> Optional[str]:
    if not ProviderConfig.OPENROUTER_API_KEY:
        return None

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {ProviderConfig.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": ProviderConfig.DEFAULT_OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"[OpenRouter] {e}")
        return None


# =========================================================
# ROUTER UNIFICADO
# =========================================================

def blackjack_executar_local(modelo: str, prompt: str) -> str:
    return _ollama_request(prompt, model=modelo or None)


async def executar(modelo: str, payload: dict) -> str:
    model = (modelo or "").lower().strip()
    prompt = payload.get("task") or payload.get("prompt") or ""

    # bandit decide o melhor modelo via router
    if not model or model == "auto":
        from iaglobal.providers.provider_router import route_generate
        return await route_generate("", prompt, task_type="general")

    # ordem de prioridade: local -> cloud -> fallback
    try:
        if model.startswith("openrouter/"):
            return _openrouter_request(prompt) or _ollama_request(prompt, model=model)

        if model.startswith("groq/"):
            return _groq_request(prompt) or _ollama_request(prompt, model=model)

        if model.startswith("gemini/") or model.startswith("nvidia/"):
            return _openrouter_request(prompt) or _ollama_request(prompt, model=ProviderConfig.DEFAULT_OLLAMA_MODEL)

        return _ollama_request(prompt, model=model)

    except Exception as e:
        logger.warning(f"[Router] {e}, falling back to local")
        return _ollama_request(prompt, model=model)


# =========================================================
# EXECUTOR PRINCIPAL
# =========================================================

class Executor:

    def __init__(self, provider: str = "ollama", max_retries: int = 3, timeout: int = 10):
        self.provider = provider
        self.max_retries = max_retries
        self.timeout = timeout
        self.history: List[Dict[str, Any]] = []

    # -----------------------------
    # LLM CALL
    # -----------------------------
    async def execute_llm(self, task: str, constraints: Optional[list] = None) -> str:
        result = await executar(self.provider, {
            "task": task,
            "system_constraints": constraints or []
        })
        return limpar_markdown(result or "")

    # -----------------------------
    # PYTHON EXECUTION
    # -----------------------------
    def execute_python(self, codigo: str, attempt: int = 0) -> ExecutionResult:

        start = time.time()

        err = validar_sintaxe(codigo)
        if err:
            return ExecutionResult(
                False, "", err, err, -1,
                time.time() - start,
                attempt, False
            )

        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(codigo)
            path = f.name

        try:
            result = subprocess.run(
                ["python", path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                traceback=result.stderr,
                return_code=result.returncode,
                execution_time=time.time() - start,
                attempt=attempt,
                validated_ast=True
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                False, "", "Timeout", "Timeout", -2,
                time.time() - start,
                attempt, True
            )

        except Exception:
            return ExecutionResult(
                False, "", "", traceback.format_exc(), -3,
                time.time() - start,
                attempt, True
            )

        finally:
            try:
                os.remove(path)
            except:
                pass

    # -----------------------------
    # SELF HEALING LOOP
    # -----------------------------
    async def autonomous_execute(self, codigo: str) -> ExecutionResult:

        current = codigo

        for i in range(1, self.max_retries + 1):

            result = self.execute_python(current, i)

            if result.success:
                return result

            fixed = await self.repair_code(current, result.traceback)
            if not fixed:
                return result

            current = fixed

        return result

    # -----------------------------
    # REPAIR AGENT
    # -----------------------------
    async def repair_code(self, codigo: str, erro: str) -> Optional[str]:

        prompt = f"""
Corrija o código Python abaixo.

CÓDIGO:
{codigo}

ERRO:
{erro}

Retorne apenas código corrigido.
"""

        try:
            fixed = await self.execute_llm(prompt)
            return fixed.strip() if len(fixed.strip()) > 5 else None
        except Exception as e:
            logger.error(f"Repair error: {e}")
            return None
