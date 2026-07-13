import httpx

from ddgs import DDGS


class SearchTools:
    @staticmethod
    async def search_and_fetch_code(query: str, max_results: int = 1) -> str:
        with DDGS() as ddgs:
            res = list(ddgs.text(f"{query} github", max_results=max_results))
            if not res:
                return "Nenhum resultado encontrado."

            url = res[0]["href"]
            if "github.com" in url:
                url = url.replace("github.com/", "raw.githubusercontent.com/").replace(
                    "/blob/", "/"
                )

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
            return (
                response.text
                if response.status_code == 200
                else "Erro ao extrair código."
            )

    @staticmethod
    def search_and_fetch_raw(query: str, max_results: int = 3) -> list[dict]:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "href": r.get("href", ""),
                        "body": r.get("body", ""),
                    }
                )
        return results
