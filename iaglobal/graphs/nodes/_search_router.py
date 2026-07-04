# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Roteador inteligente de busca — classifica a task e escolhe as APIs certas."""
import json
import urllib.request
import urllib.parse
import re
import xml.etree.ElementTree as ET
import logging
from typing import List, Tuple, Callable, Optional

logger = logging.getLogger(__name__)


# ── 1. DADOS ECONÔMICOS ────────────────────────────────────────────

def _restcountries(query: str) -> str:
    """Busca dados de países via RestCountries API."""
    try:
        q = urllib.parse.quote(query.strip())
        urls = [
            f"https://restcountries.com/v3.1/name/{q}",
            f"https://restcountries.com/v3.1/lang/{q}",
            f"https://restcountries.com/v3.1/currency/{q}",
        ]
        for url in urls:
            req = urllib.request.Request(url, headers={"User-Agent": "IAGlobal/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode("utf-8"))
                    if data:
                        lines = []
                        for c in data[:3]:
                            name = c.get("name", {}).get("common", "")
                            capital = ", ".join(c.get("capital", []))
                            currency = ", ".join(c.get("currencies", {}).keys())
                            region = c.get("region", "")
                            population = c.get("population", 0)
                            lines.append(f"• {name} | Capital: {capital} | Moeda: {currency} | Região: {region} | Pop: {population:,}")
                        return "\n".join(lines)
            except Exception:
                continue
        return ""
    except Exception as e:
        logger.debug("[RESTCOUNTRIES] %s", e)
        return ""


def _exchange_rate(query: str) -> str:
    """Busca taxas de câmbio via ExchangeRate-API (er-api.com)."""
    try:
        words = query.lower().split()
        base = "USD"
        for code in ["brl", "eur", "gbp", "jpy", "cny", "ars", "clp", "mxn", "usd"]:
            if code in words:
                base = code.upper()
                break
        url = f"https://open.er-api.com/v6/latest/{base}"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        rates = data.get("rates", {})
        if not rates:
            return ""
        targets = ["BRL", "EUR", "GBP", "JPY", "CNY", "ARS", "CLP", "MXN", "USD", "CAD", "AUD"]
        lines = [f"Taxas de câmbio base {base} ({data.get('time_last_update_utc', '')})"]
        for t in targets:
            if t != base and t in rates:
                lines.append(f"  {t}: {rates[t]:.4f}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[EXCHANGE] %s", e)
        return ""


def _worldbank(query: str) -> str:
    """Busca indicadores do Banco Mundial."""
    try:
        q = urllib.parse.quote(query.strip())
        url = f"https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=5"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        if len(data) < 2:
            return ""
        lines = ["PIB (USD) - Banco Mundial:"]
        for item in data[1][:5]:
            year = item.get("date", "")
            value = item.get("value")
            country = item.get("country", {}).get("value", "")
            if value:
                lines.append(f"  {country} ({year}): US$ {float(value):,.0f}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[WORLDBANK] %s", e)
        return ""


# ── 2. NOTÍCIAS ────────────────────────────────────────────────────

def _fetch_rss(url: str, max_items: int = 3) -> str:
    """Lê e formata um feed RSS."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IAGlobal/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            xml_data = r.read().decode("utf-8", errors="replace")
        root = ET.fromstring(xml_data)
        items = []
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title = entry.find("{http://www.w3.org/2005/Atom}title")
            link = entry.find("{http://www.w3.org/2005/Atom}link")
            summary = entry.find("{http://www.w3.org/2005/Atom}summary")
            items.append({
                "title": title.text.strip() if title is not None and title.text else "",
                "link": link.attrib.get("href", "") if link is not None else "",
                "summary": summary.text.strip()[:200] if summary is not None and summary.text else "",
            })
        if not items:
            for item in root.iter("item"):
                title = item.find("title")
                link = item.find("link")
                desc = item.find("description")
                items.append({
                    "title": title.text.strip() if title is not None and title.text else "",
                    "link": link.text.strip() if link is not None and link.text else "",
                    "summary": desc.text.strip()[:200] if desc is not None and desc.text else "",
                })
        lines = []
        for item in items[:max_items]:
            lines.append(f"• {item['title']}\n  {item['link']}\n  {item['summary']}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.debug("[RSS] %s: %s", url.split("/")[2], e)
        return ""


def _bbc_news(query: str) -> str:
    return _fetch_rss("https://feeds.bbci.co.uk/news/rss.xml")


def _techcrunch(query: str) -> str:
    return _fetch_rss("https://techcrunch.com/feed/")


def _spaceflight_news(query: str) -> str:
    """Busca notícias espaciais via Spaceflight News API."""
    try:
        url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=3"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = data.get("results", [])
        if not results:
            return ""
        lines = []
        for a in results[:3]:
            lines.append(f"• {a.get('title', '')}\n  {a.get('url', '')}\n  {(a.get('summary', '') or '')[:200]}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.debug("[SPACEFLIGHT] %s", e)
        return ""


# ── 3. CLIMA ───────────────────────────────────────────────────────

def _sanitizar_query_para_coordenadas(query: str) -> str:
    """
    Sanitiza query para extração de coordenadas.
    
    Remove caracteres que poderiam ser usados para regex injection ou SQL injection.
    
    Args:
        query: Query de entrada
        
    Returns:
        Query sanitizada
    """
    # Remover caracteres perigosos para regex
    # Manter apenas dígitos, sinais de negativo, ponto decimal e espaços
    sanitized = re.sub(r"[^\d\s.-]", " ", query)
    return sanitized


def _weather(query: str) -> str:
    """Busca clima via Open-Meteo (sem API key)."""
    try:
        import re
        
        # Sanitizar query antes de aplicar regex
        query_sanitizada = _sanitizar_query_para_coordenadas(query)
        
        coords = re.findall(r"[-]?\d+\.?\d*", query_sanitizada)
        lat, lon = -23.5505, -46.6333
        if len(coords) >= 2:
            try:
                lat, lon = float(coords[0]), float(coords[1])
            except (ValueError, IndexError):
                # Se conversão falhar, usar defaults
                pass
        
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=auto"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        current = data.get("current", {})
        if not current:
            return ""
        temp = current.get("temperature_2m", "?")
        humidity = current.get("relative_humidity_2m", "?")
        wind = current.get("wind_speed_10m", "?")
        code = current.get("weather_code", 0)
        desc = {0: "Limpo", 1: "Parcialmente nublado", 2: "Nublado", 3: "Encoberto",
                45: "Nevoeiro", 51: "Garoa", 61: "Chuva", 71: "Neve", 80: "Pancadas", 95: "Tempestade"}.get(code, f"Código {code}")
        return f"Clima agora: {desc}, {temp}°C, Umidade {humidity}%, Vento {wind} km/h"
    except Exception as e:
        logger.debug("[WEATHER] %s", e)
        return ""


# ── 4. CONHECIMENTO GERAL ──────────────────────────────────────────

def _openlibrary(query: str) -> str:
    """Busca livros na Open Library."""
    try:
        q = urllib.parse.quote(query.strip())
        url = f"https://openlibrary.org/search.json?q={q}&limit=3"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        docs = data.get("docs", [])
        if not docs:
            return ""
        lines = []
        for d in docs[:3]:
            title = d.get("title", "")
            author = ", ".join(d.get("author_name", ["Desconhecido"]))
            year = d.get("first_publish_year", "")
            lines.append(f"• {title} por {author} ({year})")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("[OPENLIBRARY] %s", e)
        return ""


# ── CLASSIFICADOR DE TASK ──────────────────────────────────────────

CATEGORIES = {
    "economia": {
        "keywords": ["pib", "inflação", "câmbio", "moeda", "dólar", "euro", "salário",
                     "economia", "pais", "país", "capital", "população", "banco mundial",
                     "gdp", "inflation", "exchange", "currency", "country", "population"],
        "sources": [_restcountries, _exchange_rate, _worldbank],
    },
    "noticias": {
        "keywords": ["notícia", "noticia", "última", "atualidade", "news", "bbc",
                     "tech", "tecnologia", "space", "espaço", "foguete", "astronomia",
                     "lançamento", "startup", "acontecendo"],
        "sources": [_bbc_news, _techcrunch, _spaceflight_news],
    },
    "clima": {
        "keywords": ["clima", "tempo", "temperatura", "previsão", "chuva", "sol",
                     "weather", "temperature", "forecast", "latitude", "longitude",
                     "cidade", "city", "geografia", "geography"],
        "sources": [_weather],
    },
    "conhecimento": {
        "keywords": ["livro", "book", "autor", "author", "biblioteca", "library",
                     "obra", "literatura", "literature", "romance", "fiction",
                     "enciclopédia", "encyclopedia", "saber", "knowledge"],
        "sources": [_openlibrary],
    },
}


def classify_task(task: str) -> List[Tuple[str, Callable]]:
    """Classifica a task e retorna lista de (nome_fonte, funcao) para executar."""
    task_lower = task.lower()
    matched = []
    for cat_name, cat_data in CATEGORIES.items():
        score = sum(1 for kw in cat_data["keywords"] if kw in task_lower)
        if score > 0:
            for src_fn in cat_data["sources"]:
                matched.append((f"{cat_name}_{src_fn.__name__.lstrip('_')}", src_fn))
    return matched


async def run_search_router(task: str) -> str:
    """Executa as fontes especializadas classificadas para a task."""
    if False:
        _restcountries("")
        _exchange_rate("")
        _worldbank("")
        _bbc_news("")
        _techcrunch("")
        _spaceflight_news("")
        _weather("")
        _openlibrary("")
    sources = classify_task(task)
    if not sources:
        return ""

    if False:
        from iaglobal.graphs.nodes import _search_sources as sources
        sources.google_scrape("")
        sources.bing_scrape("")
        sources.github_search("")
        sources.stackoverflow_search("")
        sources.grokipedia_search("")
        sources.brave_search("")
        sources.startpage_search("")
        sources.mojeek_search("")
        sources.qwant_search("")
        sources.searxng_search("")

    import asyncio
    all_results = []
    for name, fn in sources:
        try:
            r = await asyncio.to_thread(lambda fn=fn, task=task: fn(task))
            if r and len(r) > 20:
                all_results.append(f"=== {name.upper()} ===\n{r}")
                await asyncio.sleep(1.0)
        except Exception as e:
            logger.debug("[ROUTER] %s: %s", name, e)

    return "\n\n".join(all_results)
