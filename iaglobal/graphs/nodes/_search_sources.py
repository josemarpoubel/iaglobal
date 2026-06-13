"""Fontes de busca adicionais: Google, Bing, GitHub, Stack Overflow, Grokipedia, Brave, Startpage, Mojeek, Qwant."""
import json
import urllib.request
import urllib.parse
import re
import logging

from iaglobal.providers.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


def google_scrape(query: str) -> str:
    """Busca no Google via scraping simples (sem API key)."""
    try:
        query_enc = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={query_enc}&hl=en"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.5",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")

        results = []
        for match in re.finditer(r'<a[^>]*href="(/url\?q=[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
            href = match.group(1)
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            url_clean = href.split("q=")[1].split("&")[0] if "q=" in href else ""
            url_clean = urllib.parse.unquote(url_clean)
            if title and url_clean and not url_clean.startswith("http"):
                continue
            if title:
                results.append(f"• {title}\n  {url_clean}")
            if len(results) >= 3:
                break

        return "\n\n".join(results) if results else ""

    except Exception as e:
        logger.debug("[GOOGLE] Fail: %s", e)
        return ""


def bing_scrape(query: str) -> str:
    """Busca no Bing via scraping simples (sem API key)."""
    try:
        query_enc = urllib.parse.quote(query)
        url = f"https://www.bing.com/search?q={query_enc}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")

        results = []
        for match in re.finditer(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL):
            block = match.group(1)
            title_m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if title_m:
                url_bing = title_m.group(1)
                title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet_m.group(1)).strip() if snippet_m else ""
                results.append(f"• {title}\n  {url_bing}\n  {snippet}")
            if len(results) >= 3:
                break

        return "\n\n".join(results) if results else ""

    except Exception as e:
        logger.debug("[BING] Fail: %s", e)
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


def searxng_search(query: str) -> str:
    """Busca via SearXNG (meta-buscador local, agrega Google+Bing+DDG+...)."""
    import urllib.parse
    try:
        q = urllib.parse.quote(query)
        url = f"http://localhost:8080/search?q={q}&format=json&language=en"
        req = urllib.request.Request(url, headers={"User-Agent": "IAGlobal/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
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
        logger.debug("[SEARXNG] %s", e)
        return ""
