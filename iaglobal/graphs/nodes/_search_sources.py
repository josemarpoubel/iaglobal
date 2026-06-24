# iaglobal/graphs/nodes/_search_sources.py

import json
import os
import re
import time
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any

"""
Fontes de busca adicionais: Google, Bing, GitHub, Stack Overflow, Grokipedia, Brave, Startpage, Mojeek, Qwant.
Otimizado para resiliência de parsing de strings, cabeçalhos de alta fidelidade e blindagem contra IndexErrors.
"""

logger = logging.getLogger(__name__)

# Cabeçalhos modernos de alta fidelidade para contornar bloqueios anti-scraping agressivos
_MODERN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

# Regexes pré-compilados para remover tags HTML limpando lixo de renderização
_CLEAN_TAGS_REGEX = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove de forma resiliente qualquer tag HTML de uma string capturada."""
    if not text:
        return ""
    return _CLEAN_TAGS_REGEX.sub("", text).strip()


def google_scrape(query: str) -> str:
    """Busca no Google via scraping simples e parsing seguro de URL."""
    try:
        query_enc = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={query_enc}&hl=en"
        
        req = urllib.request.Request(url, headers=_MODERN_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")

        results = []
        # Captura links de resultados do Google com casamento não-guloso
        for match in re.finditer(r'<a\b[^>]*href="(/url\?q=[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
            href = match.group(1)
            title = _strip_html(match.group(2))
            
            # PARSING SEGURO: Evita o split("q=")[1] que gera IndexError
            parsed_url = urllib.parse.urlparse(href)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Obtém a URL limpa do primeiro parâmetro 'q'
            url_clean = query_params.get("q", [""])[0]
            url_clean = urllib.parse.unquote(url_clean)

            if not title or not url_clean or not url_clean.startswith("http"):
                continue

            results.append(f"• {title}\n  {url_clean}")
            if len(results) >= 3:
                break

        return "\n\n".join(results) if results else ""

    except Exception as e:
        logger.debug("[GOOGLE] Falha controlada no scraping de rede: %s", e)
        return ""


def bing_scrape(query: str) -> str:
    """Busca no Bing via scraping simples e extração resiliente de blocos."""
    try:
        query_enc = urllib.parse.quote(query)
        url = f"https://www.bing.com/search?q={query_enc}"
        
        req = urllib.request.Request(url, headers=_MODERN_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")

        results = []
        # Varre os blocos estruturais de algoritmos do Bing
        for match in re.finditer(r'<li\s+class="b_algo"\b[^>]*>(.*?)</li>', html, re.DOTALL):
            block = match.group(1)
            
            title_m = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_m = re.search(r'<p\b[^>]*>(.*?)</p>', block, re.DOTALL)
            
            if title_m:
                url_bing = title_m.group(1)
                title = _strip_html(title_m.group(2))
                snippet = _strip_html(snippet_m.group(1)) if snippet_m else ""
                
                if title and url_bing.startswith("http"):
                    results.append(f"• {title}\n  {url_bing}\n  {snippet}")
                    
            if len(results) >= 3:
                break

        return "\n\n".join(results) if results else ""

    except Exception as e:
        logger.debug("[BING] Falha controlada no scraping de rede: %s", e)
        return ""


def github_search(query: str) -> str:
    """Busca no GitHub (API pública, sem key para buscas básicas)."""
    try:
        query_enc = urllib.parse.quote(query)
        url = f"https://api.github.com/search/repositories?q={query_enc}&sort=stars&per_page=3"
        req = urllib.request.Request(url, headers={"User-Agent": "IAGlobal/1.0", "Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            import json
            data = json.loads(r.read().decode("utf-8"))

        results = []
        for item in data.get("items", [])[:3]:
            name = item.get("full_name", "")
            desc = item.get("description", "") or ""
            stars = item.get("stargazers_count", 0)
            url_repo = item.get("html_url", "")
            results.append(f"• {name} (★{stars})\n  {url_repo}\n  {desc[:200]}")
        return "\n\n".join(results) if results else ""

    except Exception as e:
        logger.debug("[GITHUB] Fail: %s", e)
        return ""


def stackoverflow_search(query: str) -> str:
    """Busca no Stack Overflow via API pública."""
    try:
        query_enc = urllib.parse.quote(query)
        url = f"https://api.stackexchange.com/2.3/search?order=desc&sort=votes&intitle={query_enc}&site=stackoverflow&filter=withbody"
        req = urllib.request.Request(url, headers={"User-Agent": "IAGlobal/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            import json
            data = json.loads(r.read().decode("utf-8"))

        results = []
        for item in data.get("items", [])[:3]:
            title = item.get("title", "")
            link = item.get("link", "")
            votes = item.get("score", 0)
            body = re.sub(r'<[^>]+>', '', item.get("body", "") or "")[:200]
            results.append(f"• {title} (▲{votes})\n  {link}\n  {body}")
        return "\n\n".join(results) if results else ""

    except Exception as e:
        logger.debug("[STACKOVERFLOW] Fail: %s", e)
        return ""


def grokipedia_search(query: str) -> str:
    """Busca na Grokipedia."""
    try:
        from grokipedia_api import GrokipediaClient
        client = GrokipediaClient()
        raw = client.search(query)
        items = raw.get("results", []) if isinstance(raw, dict) else []
        if not items:
            return ""
        lines = []
        for r in items[:3]:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            slug = r.get("slug", "")
            url = f"https://grokipedia.com/{slug}" if slug else ""
            lines.append(f"• {title}\n  {url}\n  {snippet[:300]}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.debug("[GROKIPEDIA] Fail: %s", e)
        return ""


def brave_search(query: str) -> str:
    """Busca via Brave Search API (requer BRAVE_API_KEY)."""
    key = ProviderConfig.BRAVE_API_KEY
    if not key:
        return ""
    try:
        q = urllib.parse.quote(query)
        url = f"https://api.search.brave.com/res/v1/web/search?q={q}&count=3"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "x-subscription-token": key})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = []
        for item in (data.get("web", {}) or {}).get("results", []):
            title = item.get("title", "")
            desc = item.get("description", "")
            url_r = item.get("url", "")
            results.append(f"• {title}\n  {url_r}\n  {desc[:200]}")
        return "\n\n".join(results) if results else ""
    except Exception as e:
        logger.debug("[BRAVE] %s", e)
        return ""


def startpage_search(query: str) -> str:
    """Busca no Startpage (proxy anônimo do Google)."""
    try:
        q = urllib.parse.quote(query)
        url = f"https://www.startpage.com/sp/search?query={q}&language=EN&t=device"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")
        results = []
        for match in re.finditer(r'<h3[^>]*class="[^"]*search-item__title[^"]*"[^>]*>(.*?)</h3>', html, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            results.append(f"• {title}")
            if len(results) >= 3:
                break
        return "\n\n".join(results) if results else ""
    except Exception as e:
        logger.debug("[STARTPAGE] %s", e)
        return ""


def mojeek_search(query: str) -> str:
    """Busca no Mojeek (índice próprio, sem bloqueios)."""
    try:
        q = urllib.parse.quote(query)
        url = f"https://www.mojeek.com/search?q={q}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")
        results = []
        for match in re.finditer(r'<a[^>]*href="(https?://[^"]+)"[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL):
            url_r = match.group(1)
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if title:
                results.append(f"• {title}\n  {url_r}")
            if len(results) >= 3:
                break
        return "\n\n".join(results) if results else ""
    except Exception as e:
        logger.debug("[MOJEEK] %s", e)
        return ""


def qwant_search(query: str) -> str:
    """Busca no Qwant (privacidade, França)."""
    try:
        q = urllib.parse.quote(query)
        url = f"https://www.qwant.com/?q={q}&t=web"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")
        results = []
        import json as _json
        for match in re.finditer(r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]+)</a>', html):
            url_r = match.group(1)
            title = match.group(2).strip()
            if title and url_r.startswith("http") and "qwant.com" not in url_r:
                results.append(f"• {title}\n  {url_r}")
            if len(results) >= 3:
                break
        return "\n\n".join(results) if results else ""
    except Exception as e:
        logger.debug("[QWANT] %s", e)
        return ""


# Circuit breaker para SearXNG (cache de offline)
_searxng_offline_until: float = 0.0
_searxng_fail_count: int = 0
_SEARXNG_DEFAULT_URL: str = "http://localhost:4000"


def _searxng_base_url() -> str:
    """Retorna URL base do SearXNG do ambiente ou default."""
    return os.getenv("SEARXNG_URL", _SEARXNG_DEFAULT_URL)


def _searxng_ttl() -> float:
    """Retorna TTL progressivo baseado em falhas consecutivas."""
    if _searxng_fail_count >= 3:
        return 300.0
    return 60.0


def searxng_search(query: str) -> str:
    """Busca via SearXNG (meta-buscador local, agrega Google+Bing+DDG+...).
    Inclui circuit breaker: após falha, pula tentativas por TTL progressivo.
    """
    import urllib.parse as _up

    # Circuit breaker: se offline, retorna imediatamente
    if time.monotonic() < _searxng_offline_until:
        return ""

    base = _searxng_base_url()
    try:
        q = _up.quote(query)
        url = f"{base}/search?q={q}&format=json&language=en"
        req = urllib.request.Request(url, headers={"User-Agent": "IAGlobal/1.0"})

        # Timeout reduzido se já falhou antes
        timeout = 3.0 if _searxng_fail_count > 0 else 15.0

        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))

        # Sucesso — resetar contador
        _reset_searxng_state()
        logger.info("[SEARXNG] Busca OK: %d resultados para '%.50s'", len(data.get("results", [])), query)

        results = data.get("results", [])
        if not results:
            return ""
        lines = []
        seen = set()
        for item in results[:5]:
            title = item.get("title", "")
            url_r = item.get("url", "")
            content = item.get("content", "")
            engine = item.get("engine", "")
            if title in seen:
                continue
            seen.add(title)
            lines.append(f"• {title} [{engine}]\n  {url_r}\n  {content[:200]}")
        return "\n\n".join(lines)

    except Exception as e:
        _mark_searxng_offline(e, base)
        return ""


def _reset_searxng_state():
    """Reseta contadores de falha e TTL."""
    global _searxng_offline_until, _searxng_fail_count
    _searxng_offline_until = 0.0
    _searxng_fail_count = 0


def _mark_searxng_offline(exc: Exception, base_url: str):
    """Marca SearXNG como offline com TTL progressivo e loga warning."""
    global _searxng_offline_until, _searxng_fail_count
    _searxng_fail_count += 1
    ttl = _searxng_ttl()
    _searxng_offline_until = time.monotonic() + ttl
    logger.warning(
        "[SEARXNG] Offline (falha #%d): %s — %s. "
        "Pulando por %.0fs.",
        _searxng_fail_count, base_url, exc, ttl,
    )
