# iaglobal/providers/perplexity_provider.py

from __future__ import annotations

import asyncio

from typing import Optional

from iaglobal.utils.logger import logger
from iaglobal.utils.helpers import run_async_safe
from iaglobal.utils.playwright_util import ensure_playwright_browsers

_PLAYWRIGHT = None
_BROWSER = None

_BROWSER_LOCK = asyncio.Lock()


# =============================================================================
# Browser Lifecycle
# =============================================================================


async def _ensure_browser():
    """
    Inicializa Playwright apenas uma vez.

    Thread-safe / async-safe.
    """

    global _PLAYWRIGHT, _BROWSER

    if _BROWSER is not None:
        return _BROWSER

    async with _BROWSER_LOCK:
        if _BROWSER is not None:
            return _BROWSER

        ensure_playwright_browsers(["firefox"])

        from playwright.async_api import async_playwright

        logger.info("[PERPLEXITY] Inicializando navegador")

        _PLAYWRIGHT = await async_playwright().start()

        _BROWSER = await _PLAYWRIGHT.firefox.launch(
            headless=True,
            args=[
                "--no-sandbox",
            ],
        )

        logger.info("[PERPLEXITY] Navegador inicializado")

        return _BROWSER


# =============================================================================
# Page Factory
# =============================================================================


async def _new_page():

    browser = await _ensure_browser()

    context = await browser.new_context()

    page = await context.new_page()

    return context, page


# =============================================================================
# Main API
# =============================================================================


def generate(
    prompt: str,
    model: str = "perplexity/default",
    timeout: int = 60,
    token_collector: Optional[callable] = None,
) -> str:
    return run_async_safe(async_generate, prompt, model, timeout, token_collector)


async def async_generate(
    prompt: str,
    model: str = "perplexity/default",
    timeout: int = 60,
    token_collector: Optional[callable] = None,
) -> str:

    context = None
    page = None

    try:
        context, page = await _new_page()

        goto_timeout_ms = min(
            max(timeout * 1000, 15000),
            60000,
        )

        logger.debug(
            "[PERPLEXITY] Nova sessão criada timeout=%ss",
            timeout,
        )

        await page.goto(
            "https://www.perplexity.ai",
            wait_until="domcontentloaded",
            timeout=goto_timeout_ms,
        )

        await asyncio.sleep(2)

        # ---------------------------------------------------------------------
        # Cookies banner
        # ---------------------------------------------------------------------

        try:
            allow_btn = await page.query_selector('button:has-text("Allow all")')

            if allow_btn:
                await allow_btn.click()
                await asyncio.sleep(1)

        except Exception:
            pass

        # ---------------------------------------------------------------------
        # Input
        # ---------------------------------------------------------------------

        input_el = await page.query_selector('[contenteditable="true"]')

        if not input_el:
            input_el = await page.query_selector("textarea")

        if not input_el:
            logger.warning("[PERPLEXITY] Campo de entrada não encontrado")

            return ""

        await input_el.fill(prompt)

        await asyncio.sleep(0.3)

        await page.keyboard.press("Enter")

        logger.debug(
            "[PERPLEXITY] Prompt enviado (%d chars)",
            len(prompt),
        )

        # ---------------------------------------------------------------------
        # Wait response
        # ---------------------------------------------------------------------

        max_cycles = max(
            5,
            timeout // 2,
        )

        for _ in range(max_cycles):
            await asyncio.sleep(2)

            try:
                body = await page.text_content("body")

            except Exception:
                continue

            body = body or ""

            body = " ".join(body.split())

            body_lower = body.lower()

            # -------------------------------------------------------------
            # Login wall
            # -------------------------------------------------------------

            if (
                "sign in to generate web apps" in body_lower
                or "exclusive access to web app generation" in body_lower
            ):
                logger.warning("[PERPLEXITY] Login obrigatório")

                return ""

            # -------------------------------------------------------------
            # Response markers
            # -------------------------------------------------------------

            if "sources" not in body_lower and "follow-up" not in body_lower:
                continue

            prompt_clean = prompt.strip()

            if not prompt_clean:
                continue

            idx = body.rfind(prompt_clean)

            if idx < 0:
                prompt_key = prompt_clean.split()[0]

                idx = body.rfind(prompt_key)

                if idx < 0:
                    continue

            src_idx = body_lower.rfind("sources")

            if src_idx < 0:
                continue

            if src_idx <= idx:
                continue

            raw = body[idx:src_idx].strip()

            if raw.startswith(prompt_clean):
                raw = raw[len(prompt_clean) :].strip()

            raw = raw.rstrip("0123456789. ")

            noise = (
                "Sign In",
                "Answer",
                "Links",
                "Images",
                "Share",
                "Search",
                "Model",
                "Computer",
                "Pro",
                "New",
                "Spaces",
                "History",
                "Workflows",
                "Skills",
                "Connectors",
                "Customize",
                "Artifacts",
            )

            for n in noise:
                raw = raw.replace(n, "")

            raw = " ".join(raw.split()).strip()

            if raw:
                logger.debug(
                    "[PERPLEXITY] Resposta recebida (%d chars)",
                    len(raw),
                )

                if token_collector:
                    try:
                        token_collector(0, 0)
                    except Exception:
                        pass

                return raw

        logger.warning("[PERPLEXITY] Timeout aguardando resposta")

        return ""

    except asyncio.CancelledError:
        logger.debug("[PERPLEXITY] Task cancelada")

        raise

    except Exception as e:
        logger.warning(
            "[PERPLEXITY] %s",
            e,
        )

        return ""

    finally:
        try:
            if page and not page.is_closed():
                await page.close()

        except Exception:
            pass

        try:
            if context:
                await context.close()

        except Exception:
            pass
