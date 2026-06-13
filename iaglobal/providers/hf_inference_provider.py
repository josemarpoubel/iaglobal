# iaglobal/providers/hf_inference_provider.py

from __future__ import annotations

import asyncio

from typing import Optional

from huggingface_hub import InferenceClient

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.utils.logger import logger


# =============================================================================
# Singleton Client
# =============================================================================

_CLIENT: Optional[InferenceClient] = None


def _get_client() -> Optional[InferenceClient]:
    """
    Reutiliza o mesmo cliente HF ao longo do processo.
    """

    global _CLIENT

    api_key = ProviderConfig.HUGGINGFACE_API_KEY

    if not api_key:
        return None

    if _CLIENT is None:

        _CLIENT = InferenceClient(
            api_key=api_key,
        )

    return _CLIENT


# =============================================================================
# Helpers
# =============================================================================

def _extract_result(completion) -> str:

    try:

        choices = getattr(
            completion,
            "choices",
            None,
        )

        if not choices:
            return ""

        message = getattr(
            choices[0],
            "message",
            None,
        )

        if not message:
            return ""

        content = getattr(
            message,
            "content",
            "",
        )

        return (content or "").strip()

    except Exception:

        return ""


def _collect_tokens(
    completion,
    token_collector: Optional[TokenCollector],
) -> None:

    if not token_collector:
        return

    try:

        usage = getattr(
            completion,
            "usage",
            None,
        )

        if not usage:
            return

        token_collector(
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )

    except Exception as exc:

        logger.debug(
            "[HFInference] token collection failed: %s",
            exc,
        )


def _estimate_max_tokens(prompt: str) -> int:
    """
    Heurística simples para evitar pedir 4096 tokens
    para prompts minúsculos.
    """

    size = len(prompt)

    if size < 100:
        return 512

    if size < 1000:
        return 1024

    if size < 5000:
        return 2048

    return 4096


# =============================================================================
# Main API
# =============================================================================

async def async_generate(
    prompt: str,
    model: str = "hf_inference/openai/gpt-oss-20b:groq",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None,
) -> str:

    client = _get_client()

    if not client:

        logger.debug(
            "[HFInference] API key não configurada"
        )

        return ""

    model = (
        model
        .replace("hf_inference/", "", 1)
        .strip()
    )

    if not model:

        model = (
            "openai/gpt-oss-20b:groq"
        )

    max_tokens = _estimate_max_tokens(
        prompt
    )

    logger.info(
        "[HFInference] model=%s timeout=%ss prompt_len=%d max_tokens=%d",
        model,
        timeout,
        len(prompt),
        max_tokens,
    )

    try:

        def _call():

            return client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                max_tokens=max_tokens,
            )

        completion = await asyncio.wait_for(
            asyncio.to_thread(_call),
            timeout=timeout,
        )

        result = _extract_result(
            completion
        )

        _collect_tokens(
            completion,
            token_collector,
        )

        logger.info(
            "[HFInference] model=%s response_len=%d",
            model,
            len(result),
        )

        return result

    except asyncio.TimeoutError:

        logger.warning(
            "[HFInference] timeout model=%s timeout=%ss",
            model,
            timeout,
        )

        return ""

    except Exception as exc:

        error_code = getattr(
            exc,
            "status_code",
            None,
        )

        if error_code:

            logger.warning(
                "[HFInference] HTTP %s model=%s error=%s",
                error_code,
                model,
                exc,
            )

        else:

            logger.warning(
                "[HFInference] model=%s error=%s",
                model,
                exc,
            )

        return ""
