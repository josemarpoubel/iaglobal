# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Fontes de busca aprimoradas: DDGS para URLs, Playwright para JS, BS4 para extracao."""
import asyncio
import logging
import time
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from iaglobal._paths import DATA_DIR
from iaglobal.utils.logger import logger
from iaglobal.utils.playwright_util import ensure_playwright_browsers

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 12
_MAX_RESULTS = 3


# ── HTML fetch + parse via BeautifulSoup ─────────────────────────────

def _bs4_extract_text(html: str, url: str = "") -> str:
    """Extrai texto limpo de HTML usando BeautifulSoup."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                      "noscript", "iframe", "svg", "form", "button"]):
        tag.decompose()

    lines = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li",
                               "pre", "code", "blockquote", "td", "th"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 15:
            lines.append(text)

    text = "\n".join(lines)
    if len(text) > 5000:
        text = text[:5000]

    domain = urlparse(url).netloc if url else ""
    return f"[{domain}]\n{text}" if domain else text


async def _fetch_page(url: str) -> str:
    """Faz HTTP GET e extrai texto com BS4."""
    try:
        headers = {
            "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT)) as resp:
                text = await resp.text()
                return _bs4_extract_text(text, url)
    except Exception as e:
        logger.debug("[FETCH] Falha ao buscar %s: %s", url, e)
        return ""


# ── Obter URLs via DDGS (confiavel, nao bloqueia) ────────────────────

def _search_urls(query: str, max_results: int = _MAX_RESULTS) -> list[str]:
    """Retorna URLs de resultados de busca usando DuckDuckGo (DDGS)."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [r["href"] for r in results if r.get("href")]
    except Exception as e:
        logger.debug("[URLS] DDGS falhou: %s", e)
        pass

    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [r["href"] for r in results if r.get("href")]
    except Exception as e:
        logger.debug("[URLS] duckduckgo_search falhou: %s", e)

    return []


# ── DDGS + BS4 (para paginas HTML simples) ───────────────────────────

async def ddg_enhanced_search(query: str) -> str:
    """Busca com DDGS + BS4: obtem URLs, extrai conteudo de cada pagina."""
    urls = _search_urls(query)
    if not urls:
        return ""

    results = []
    for url in urls:
        content = await _fetch_page(url)
        if content:
            results.append(f"• {url}\n{content[:800]}")

    return "\n\n---\n\n".join(results) if results else ""


async def bs4_deep_search(query: str) -> str:
    """Busca com DDGS + BS4 profundo: extrai ate 1000 chars por pagina."""
    urls = _search_urls(query)
    if not urls:
        return ""

    results = []
    for url in urls:
        content = await _fetch_page(url)
        if content and len(content) > 100:
            results.append(content[:1000])

    return "\n\n---\n\n".join(results) if results else ""


# ── Playwright (para paginas JS-heavy) ───────────────────────────────

def _playwright_fetch_page(url: str, wait_ms: int = 2000) -> str:
    """Renderiza URL com Playwright Chromium headless e extrai texto com BS4.

    Ideal para SPAs, React, paginas com carregamento JS assincrono.
    Playwright evita deteccao de bot muito melhor que Selenium.
    """
    if not ensure_playwright_browsers():
        logger.debug("[PLAYWRIGHT] playwright nao disponivel")
        return ""

    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (X11; Linux x86_64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            page.goto(url, timeout=_HTTP_TIMEOUT * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            html = page.content()
            browser.close()
        return _bs4_extract_text(html, url)
    except Exception as e:
        logger.debug("[PLAYWRIGHT] Falha ao renderizar %s: %s", url, e)
        return ""


def playwright_search(query: str) -> str:
    """Busca com DDGS + Playwright: renderiza cada URL com JS.

    Fornece conteudo de paginas que exigem JavaScript (SPAs, React, etc.).
    """
    urls = _search_urls(query)
    if not urls:
        return ""

    results = []
    for url in urls:
        content = _playwright_fetch_page(url)
        if content:
            results.append(f"[renderizado]\n{content[:1000]}")

    return "\n\n---\n\n".join(results) if results else ""


# ── Screenshot via Playwright ────────────────────────────────────────

def playwright_screenshot(url: str, output_path: Optional[str] = None) -> Optional[str]:
    """Tira screenshot full-page de uma URL com Playwright."""
    if not ensure_playwright_browsers():
        return None

    from playwright.sync_api import sync_playwright

    if not output_path:
        ts = int(time.time())
        output_path = str(DATA_DIR / "cache" / "search_swap" / f"screenshot_{ts}.png")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, timeout=_HTTP_TIMEOUT * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.screenshot(path=output_path, full_page=True)
            browser.close()
        return output_path
    except Exception as e:
        logger.debug("[SCREENSHOT] Erro: %s", e)
        return None
