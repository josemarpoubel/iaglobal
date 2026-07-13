# iaglobal/providers/hf_video_provider.py

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from threading import Lock
from typing import Optional

from huggingface_hub import InferenceClient

from iaglobal._paths import TEMP_DIR
from iaglobal.providers.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# =============================================================================
# Sync wrapper for router compatibility
# =============================================================================


def text_to_video(
    prompt: str,
    model: str = "hf_video/wan2.1",
    provider: str = "auto",
    timeout: int = 300,
) -> Optional[str]:
    """Sync wrapper for direct video generation calls."""
    return asyncio.run(text_to_video_async(prompt, model, provider, timeout))


def generate(
    prompt: str,
    model: str = "hf_video/wan2.1",
    timeout: int = 300,
    provider: str = "auto",
) -> Optional[str]:
    """Sync wrapper for router compatibility - mimics other providers."""
    return asyncio.run(text_to_video_async(prompt, model, timeout, provider))


# =============================================================================
# Directory Setup
# =============================================================================

VIDEOS_DIR = TEMP_DIR / "generated_videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Predefined Model Aliases (must be defined before _resolve_model)
# =============================================================================

VIDEO_MODELS = {
    # Text-to-Video generation
    "wan2.1": "Wan-AI/Wan2.1-T2V-14B",
    "wan2.2": "Wan-AI/Wan2.2",
    "ltx": "Lightricks/LTX-Video",
    "hunyuan": "tencent/HunyuanVideo",
    # Video-to-Text analysis (VLM)
    "qwen2vl": "Qwen/Qwen2-VL-7B-Instruct",
    "qwen2.5vl": "Qwen/Qwen2.5-VL-7B-Instruct",
    "llava-video": "LLaVA-Video-7B-Qwen2",
}


# =============================================================================
# Client Cache (Thread-Safe)
# =============================================================================

_CLIENTS: dict[str, InferenceClient] = {}
_CLIENT_LOCK = Lock()


def _get_client(provider: str = "auto") -> Optional[InferenceClient]:
    """Get or create a thread-safe cached InferenceClient for video operations."""
    api_key = getattr(ProviderConfig, "HUGGINGFACE_API_KEY", None)

    if not api_key:
        logger.warning("[HFVideo] HUGGINGFACE_API_KEY not configured")
        return None

    cache_key = f"hf_video:{provider}:{api_key}"

    with _CLIENT_LOCK:
        client = _CLIENTS.get(cache_key)
        if client is not None:
            return client

        client = InferenceClient(
            api_key=api_key,
            provider=provider,
        )
        _CLIENTS[cache_key] = client
        return client


def _resolve_model(model_alias: str) -> str:
    """Resolve model alias (hf_video/wan2.1) to actual HF model ID."""
    if model_alias.startswith("hf_video/"):
        alias = model_alias.split("/", 1)[1]
        return VIDEO_MODELS.get(alias, alias)
    return model_alias


def _extract_provider_from_model(model: str) -> str:
    """Extract provider from model string (e.g., 'hf_video/wan2.1' -> 'auto')."""
    return "auto"  # use default HF provider routing


async def text_to_video_async(
    prompt: str,
    model: str = "Wan-AI/Wan2.1-T2V-14B",
    timeout: int = 300,
    provider: str = "auto",
) -> Optional[str]:
    """Async video generation - runs blocking I/O via to_thread."""
    start_time = time.monotonic()

    # Handle model format: hf_video/wan2.1 -> extract and resolve
    if model.startswith("hf_video/"):
        provider = _extract_provider_from_model(model)
        model = _resolve_model(model)

    client = _get_client(provider)
    if client is None:
        return None

    try:
        logger.info(
            "[HFVideo] text_to_video model=%s provider=%s prompt_len=%d",
            model,
            provider,
            len(prompt),
        )

        # Run blocking I/O in thread pool
        video_path = await asyncio.to_thread(
            _generate_video_blocking,
            client,
            prompt,
            model,
        )

        latency = time.monotonic() - start_time

        if video_path:
            logger.info(
                "[HFVideo] video saved=%s latency=%.2fs",
                video_path,
                latency,
            )
        else:
            logger.warning("[HFVideo] provider returned empty video")
            return None

        return video_path

    except Exception as exc:
        latency = time.monotonic() - start_time
        error_code = getattr(exc, "status_code", None)

        logger.warning(
            "[HFVideo] text_to_video error model=%s provider=%s error=%s",
            model,
            provider,
            exc,
        )
        return None


def _generate_video_blocking(
    client: InferenceClient,
    prompt: str,
    model: str,
) -> Optional[str]:
    """Blocking I/O wrapper for video generation."""
    try:
        # Use text_to_video method (available in newer huggingface_hub)
        video = client.text_to_video(
            prompt,
            model=model,
        )

        if video is None:
            return None

        filename = f"{uuid.uuid4().hex}.mp4"
        filepath = VIDEOS_DIR / filename

        # Save video bytes
        if hasattr(video, "read"):
            # It's a file-like object
            video_bytes = video.read()
        elif isinstance(video, (bytes, bytearray)):
            video_bytes = bytes(video)
        elif isinstance(video, str):
            # If it returns a URL, download it
            import requests

            response = requests.get(video, timeout=60)
            if response.ok:
                video_bytes = response.content
            else:
                return None
        else:
            return None

        with open(filepath, "wb") as f:
            f.write(video_bytes)

        return str(filepath)

    except Exception as exc:
        logger.error("[HFVideo] Blocking generation failed: %s", exc)
        return None


# =============================================================================
# Video Analysis (Video-to-Text) - VLM Models
# =============================================================================


def analyze_video(
    video_path: str,
    prompt: str = "Describe what happens in this video.",
    model: str = "Qwen/Qwen2-VL-7B-Instruct",
    provider: str = "auto",
    timeout: int = 120,
) -> Optional[str]:
    """
    Analyze video content using VLM (Qwen2-VL, Qwen2.5-VL, LLaVA-Video).

    Extracts temporal understanding, actions, and answers questions about video content.
    """
    import asyncio

    async def _async_analyze():
        return await analyze_video_async(video_path, prompt, model, provider, timeout)

    return asyncio.run(_async_analyze())


async def analyze_video_async(
    video_path: str,
    prompt: str = "Describe what happens in this video.",
    model: str = "Qwen/Qwen2-VL-7B-Instruct",
    provider: str = "auto",
    timeout: int = 120,
) -> Optional[str]:
    """Async video analysis - runs blocking I/O via to_thread."""
    start_time = time.monotonic()

    client = _get_client(provider)
    if client is None:
        return None

    try:
        logger.info(
            "[HFVideo] analyze_video model=%s provider=%s",
            model,
            provider,
        )

        # Run blocking I/O in thread pool
        result = await asyncio.to_thread(
            _analyze_video_blocking,
            client,
            video_path,
            prompt,
            model,
        )

        latency = time.monotonic() - start_time

        logger.info(
            "[HFVideo] analyzed video latency=%.2fs",
            latency,
        )

        return result

    except Exception as exc:
        latency = time.monotonic() - start_time
        logger.warning(
            "[HFVideo] analyze_video error model=%s provider=%s error=%s",
            model,
            provider,
            exc,
        )
        return None


def _analyze_video_blocking(
    client: InferenceClient,
    video_path: str,
    prompt: str,
    model: str,
) -> Optional[str]:
    """Blocking I/O wrapper for video analysis."""
    try:
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        # Use chat method with video input for VLM models
        result = client.chat(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "video", "video": video_bytes},
                    ],
                }
            ],
            model=model,
        )

        if result and hasattr(result, "choices"):
            return result.choices[0].message.content

        return str(result) if result else None

    except Exception as exc:
        logger.error("[HFVideo] Blocking analysis failed: %s", exc)
        return None
