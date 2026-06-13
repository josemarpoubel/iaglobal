# iaglobal/providers/hf_image_provider.py

from __future__ import annotations

import time
import uuid

from pathlib import Path
from typing import Optional

from huggingface_hub import InferenceClient

from iaglobal._paths import IMAGES_DIR
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.utils.logger import logger

try:
    from iaglobal.providers.provider_state import provider_state
except Exception:
    provider_state = None


IMAGES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =============================================================================
# Client Cache
# =============================================================================

_CLIENTS: dict[str, InferenceClient] = {}


def _get_client(
    provider: str,
) -> Optional[InferenceClient]:

    api_key = getattr(
        ProviderConfig,
        "HUGGINGFACE_API_KEY",
        None,
    )

    if not api_key:

        logger.warning(
            "[HFImage] HUGGINGFACE_API_KEY não configurada"
        )

        return None

    cache_key = f"{provider}:{api_key}"

    client = _CLIENTS.get(
        cache_key
    )

    if client is not None:
        return client

    client = InferenceClient(
        api_key=api_key,
        provider=provider,
    )

    _CLIENTS[cache_key] = client

    return client


# =============================================================================
# Image Generation
# =============================================================================

def text_to_image(
    prompt: str,
    model: str = "black-forest-labs/FLUX.1-schnell",
    provider: str = "nscale",
    timeout: int = 60,
) -> Optional[str]:

    start_time = time.monotonic()

    client = _get_client(
        provider
    )

    if client is None:
        return None

    try:

        logger.info(
            "[HFImage] model=%s provider=%s prompt_len=%d",
            model,
            provider,
            len(prompt),
        )

        image = client.text_to_image(
            prompt,
            model=model,
        )

        if image is None:

            logger.warning(
                "[HFImage] provider retornou imagem vazia"
            )

            return None

        filename = (
            f"{uuid.uuid4().hex}.png"
        )

        filepath = (
            IMAGES_DIR / filename
        )

        image.save(
            str(filepath)
        )

        latency = (
            time.monotonic()
            - start_time
        )

        logger.info(
            "[HFImage] imagem salva=%s latency=%.2fs",
            filepath,
            latency,
        )

        if provider_state:

            try:

                provider_state.update(
                    provider="hf",
                    success=True,
                    latency=latency,
                )

            except Exception:
                pass

        return str(filepath)

    except Exception as exc:

        latency = (
            time.monotonic()
            - start_time
        )

        error_code = getattr(
            exc,
            "status_code",
            None,
        )

        logger.warning(
            "[HFImage] model=%s provider=%s error=%s",
            model,
            provider,
            exc,
        )

        if provider_state:

            try:

                provider_state.update(
                    provider="hf",
                    success=False,
                    latency=latency,
                    error_code=error_code,
                )

            except Exception:
                pass

        return None


# =============================================================================
# Rich API
# =============================================================================

def text_to_image_metadata(
    prompt: str,
    model: str = "black-forest-labs/FLUX.1-schnell",
    provider: str = "nscale",
    timeout: int = 60,
) -> Optional[dict]:

    path = text_to_image(
        prompt=prompt,
        model=model,
        provider=provider,
        timeout=timeout,
    )

    if not path:
        return None

    try:

        size_bytes = Path(path).stat().st_size

    except Exception:

        size_bytes = 0

    return {
        "path": path,
        "model": model,
        "provider": provider,
        "prompt": prompt,
        "size_bytes": size_bytes,
    }
