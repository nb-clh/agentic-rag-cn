import httpx
import asyncio
import os


class WebRetriever:
    def __init__(self, searxng_url=None):
        self.searxng_url = searxng_url or os.getenv("SEARXNG_URL", "http://localhost:8080")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str, num_results: int = 10):
        try:
            resp = await self.client.get(
                f"{self.searxng_url}/search",
                params={"q": query, "format": "json", "pageno": 1}
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "source": item.get("engine", "unknown")
                })
            return results
        except Exception as e:
            return [{"error": str(e)}]
