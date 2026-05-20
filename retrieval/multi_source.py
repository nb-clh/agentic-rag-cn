import httpx
import asyncio
from bs4 import BeautifulSoup


class MultiSourceSearch:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    async def search_zhihu(self, query: str):
        try:
            resp = await self.client.get(
                "https://www.zhihu.com/search",
                params={"type": "content", "q": query}
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for item in soup.select(".SearchResult-Card")[:5]:
                    title = item.select_one("h2")
                    content = item.select_one(".RichContent-inner")
                    if title:
                        results.append({
                            "title": title.get_text(strip=True),
                            "content": content.get_text(strip=True) if content else "",
                            "source": "zhihu"
                        })
                return results
            return []
        except Exception as e:
            return [{"error": f"zhihu: {e}"}]

    async def search_bilibili(self, query: str):
        try:
            resp = await self.client.get(
                "https://api.bilibili.com/x/web-interface/search/all/v2",
                params={"keyword": query}
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("data", {}).get("result", [])[:5]:
                    if item.get("result_type") == "video":
                        for video in item.get("data", [])[:3]:
                            title = BeautifulSoup(video.get("title", ""), "html.parser").get_text()
                            results.append({
                                "title": title,
                                "content": video.get("description", ""),
                                "url": f"https://www.bilibili.com/video/{video.get('bvid', '')}",
                                "source": "bilibili"
                            })
                return results
            return []
        except Exception as e:
            return [{"error": f"bilibili: {e}"}]

    async def search_v2ex(self, query: str):
        """V2EX 搜索 - 通过 API"""
        try:
            resp = await self.client.get(
                "https://www.v2ex.com/api/topics/search.json",
                params={"q": query}
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data[:5]:
                    title = item.get("title", "")
                    content = item.get("content", "")
                    results.append({
                        "title": title,
                        "content": content[:200] if content else "",
                        "url": f"https://www.v2ex.com/t/{item.get('id', '')}",
                        "source": "v2ex"
                    })
                return results
            return []
        except Exception as e:
            return [{"error": f"v2ex: {e}"}]

    async def search_github(self, query: str):
        """GitHub 搜索 - 通过 API（仓库 + Issues）"""
        try:
            # 搜索仓库
            repo_resp = await self.client.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "per_page": 5}
            )
            results = []
            if repo_resp.status_code == 200:
                for item in repo_resp.json().get("items", [])[:5]:
                    results.append({
                        "title": item.get("full_name", ""),
                        "content": item.get("description", "") or "",
                        "url": item.get("html_url", ""),
                        "source": "github"
                    })
            # 搜索 Issues
            issue_resp = await self.client.get(
                "https://api.github.com/search/issues",
                params={"q": query, "sort": "reactions", "per_page": 3}
            )
            if issue_resp.status_code == 200:
                for item in issue_resp.json().get("items", [])[:3]:
                    results.append({
                        "title": item.get("title", ""),
                        "content": (item.get("body", "") or "")[:200],
                        "url": item.get("html_url", ""),
                        "source": "github"
                    })
            return results
        except Exception as e:
            return [{"error": f"github: {e}"}]

    async def search_all(self, query: str):
        zhihu, bili, v2ex, github = await asyncio.gather(
            self.search_zhihu(query),
            self.search_bilibili(query),
            self.search_v2ex(query),
            self.search_github(query),
            return_exceptions=True
        )
        results = []
        for r in [zhihu, bili, v2ex, github]:
            if isinstance(r, list):
                results.extend(r)
        return results
