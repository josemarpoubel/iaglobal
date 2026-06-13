"""Wikipedia search helper — shared between consolidated and standalone nodes."""
import json
import urllib.parse
import aiohttp


async def _wikipedia_async(query: str) -> str:
    params = urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": 3
    })
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    headers = {"User-Agent": "IAGlobal/1.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
    results = []
    for item in data.get("query", {}).get("search", []):
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', ''))}",
        })
    if not results:
        return ""
    lines = [f"• {r['title']}\n  {r['url']}\n  {r['snippet']}" for r in results]
    return "\n\n".join(lines)
