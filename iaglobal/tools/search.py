from iaglobal.tools.search_tools import SearchTools
from iaglobal.memory.db_manager import db
from iaglobal.utils.logger import logger

def search_tool(query: str) -> str:
    cache_key = f"search_tool:{hash(query)}"
    cached = db.get_cached_search(cache_key)
    if cached:
        logger.info(f"🧠 [SEARCH TOOL]: Cache hit para '{query[:60]}...'")
        return cached

    try:
        snippets = SearchTools.search_and_fetch_raw(query, max_results=3)
        if snippets:
            result = "\n\n".join(
                f"• {s['title']}\n  {s['href']}\n  {s['body']}"
                for s in snippets
            )
        else:
            result = SearchTools.search_and_fetch_code(query)
    except Exception as e:
        logger.warning(f"[SEARCH TOOL]: Fallback — {e}")
        return f"Resultados encontrados para: {query} (Simulação)"

    if result and "Nenhum" not in result and "Erro" not in result:
        db.cache_search_result(cache_key, result)

    return result
