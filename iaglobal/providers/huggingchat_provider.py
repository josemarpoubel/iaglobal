# iaglobal/providers/huggingchat_provider.py

from __future__ import annotations

import asyncio

from typing import Optional

from iaglobal.utils.logger import logger

_PLAYWRIGHT = None
_BROWSER = None

_BROWSER_LOCK = asyncio.Lock()


# =============================================================================
# Browser Lifecycle
# =============================================================================

async def _ensure_browser():

    global _PLAYWRIGHT
    global _BROWSER

    if _BROWSER is not None:
        return _BROWSER

    async with _BROWSER_LOCK:

        if _BROWSER is not None:
            return _BROWSER

        from playwright.async_api import async_playwright

        logger.info(
            "[HUGGINGCHAT] Inicializando navegador"
        )

        _PLAYWRIGHT = await async_playwright().start()

        _BROWSER = await _PLAYWRIGHT.firefox.launch(
            headless=True,
            args=[
                "--no-sandbox",
            ],
        )

        logger.info(
            "[HUGGINGCHAT] Navegador inicializado"
        )

        return _BROWSER


# =============================================================================
# Context/Page Factory
# =============================================================================

async def _new_page():

    browser = await _ensure_browser()

    context = await browser.new_context()

    page = await context.new_page()

    return context, page


# =============================================================================
# Main API
# =============================================================================

async def async_generate(
    prompt: str,
    model: str = "huggingchat/default",
    timeout: int = 90,
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

        await page.goto(
            "https://huggingface.co/chat",
            wait_until="domcontentloaded",
            timeout=goto_timeout_ms,
        )

        await asyncio.sleep(3)

        # ---------------------------------------------------------------------
        # Input
        # ---------------------------------------------------------------------

        input_el = await page.query_selector(
            'textarea[placeholder="Ask anything"]'
        )

        if not input_el:

            input_el = await page.query_selector(
                "textarea"
            )

        if not input_el:

            logger.warning(
                "[HUGGINGCHAT] Campo de entrada não encontrado"
            )

            return ""

        await input_el.fill(
            prompt
        )

        await asyncio.sleep(0.5)

        await page.keyboard.press(
            "Enter"
        )

        logger.debug(
            "[HUGGINGCHAT] Prompt enviado (%d chars)",
            len(prompt),
        )

        # ---------------------------------------------------------------------
        # Wait Response
        # ---------------------------------------------------------------------

        max_cycles = max(
            5,
            timeout // 2,
        )

        previous_response = ""

        for _ in range(max_cycles):

            await asyncio.sleep(2)

            try:

                stop_btn = await page.query_selector(
                    'button:has-text("Stop")'
                )

                if stop_btn:
                    continue

            except Exception:
                pass

            try:

                texts = await page.evaluate(
                    """
                    () => {

                        const selectors = [
                            '.prose',
                            '.markdown',
                            '[class*="prose"]'
                        ];

                        let result = [];

                        selectors.forEach(selector => {

                            document
                                .querySelectorAll(selector)
                                .forEach(el => {

                                    const text =
                                        el.textContent?.trim();

                                    if (
                                        text &&
                                        text.length > 10
                                    ) {
                                        result.push(text);
                                    }
                                });
                        });

                        return result;
                    }
                    """
                )

            except Exception:

                continue

            if not texts:
                continue

            texts = [
                t.strip()
                for t in texts
                if t and len(t.strip()) > 10
            ]

            if not texts:
                continue

            candidate = texts[-1].strip()

            if not candidate:
                continue

            # Evita retornar o próprio prompt

            if candidate == prompt.strip():
                continue

            if candidate.startswith(
                prompt.strip()
            ):
                candidate = candidate[
                    len(prompt.strip()):
                ].strip()

            # Aguarda estabilização da resposta

            if candidate != previous_response:

                previous_response = candidate

                continue

            logger.debug(
                "[HUGGINGCHAT] Resposta recebida (%d chars)",
                len(candidate),
            )

            if token_collector:

                try:
                    token_collector(0, 0)
                except Exception:
                    pass

            return candidate

        logger.warning(
            "[HUGGINGCHAT] Timeout aguardando resposta"
        )

        return ""

    except asyncio.CancelledError:

        logger.debug(
            "[HUGGINGCHAT] Task cancelada"
        )

        raise

    except Exception as e:

        logger.warning(
            "[HUGGINGCHAT] %s",
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


# =============================================================================
# Shutdown
# =============================================================================

async def shutdown_browser():

    global _PLAYWRIGHT
    global _BROWSER

    async with _BROWSER_LOCK:

        try:

            if _BROWSER:

                await _BROWSER.close()

        except Exception:
            pass

        try:

            if _PLAYWRIGHT:

                await _PLAYWRIGHT.stop()

        except Exception:
            pass

        _BROWSER = None
        _PLAYWRIGHT = None

        logger.info(
            "[HUGGINGCHAT] Navegador encerrado"
        )
