"""搜索服务：API 搜索 + Playwright 爬虫。"""
from core.config import settings
from typing import List


async def search_api(query: str, site_filter: List[str] | None = None) -> List[dict]:
    """调用搜索 API，返回 [{title, url, content}]。"""
    p = settings.SEARCH_API_PROVIDER

    if p == "tavily":
        return await _tavily_search(query, site_filter)
    if p == "serpapi":
        return await _serpapi_search(query, site_filter)
    if p == "bing":
        return await _bing_search(query, site_filter)
    return []


async def crawl_sites(sites: List[str], queries: List[str]) -> List[dict]:
    """用 Playwright 爬取指定网站，提取与 queries 相关的内容。"""
    if not settings.CRAWLER_ENABLED:
        return []

    from playwright.async_api import async_playwright
    from bs4 import BeautifulSoup

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
        page = await browser.new_page()

        for site in sites[:5]:  # 限制最多 5 个站点
            try:
                await page.goto(site, timeout=15000, wait_until="domcontentloaded")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(separator="\n", strip=True)[:3000]
                results.append({"title": soup.title.string if soup.title else site, "url": site, "content": text})
            except Exception:
                pass

        await browser.close()
    return results


async def _tavily_search(query: str, site_filter: List[str] | None) -> List[dict]:
    from tavily import AsyncTavilyClient

    client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
    params = {"query": query, "max_results": 10, "search_depth": "advanced"}
    if site_filter:
        params["include_domains"] = site_filter

    resp = await client.search(**params)
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in resp.get("results", [])
    ]


async def _serpapi_search(query: str, site_filter: List[str] | None) -> List[dict]:
    import httpx

    q = query
    if site_filter:
        q += " site:" + " OR site:".join(site_filter)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={"q": q, "api_key": settings.SERPAPI_KEY, "num": 10},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {"title": r.get("title", ""), "url": r.get("link", ""), "content": r.get("snippet", "")}
        for r in data.get("organic_results", [])
    ]


async def _bing_search(query: str, site_filter: List[str] | None) -> List[dict]:
    import httpx

    q = query
    if site_filter:
        q += " site:" + " OR site:".join(site_filter)

    headers = {"Ocp-Apim-Subscription-Key": settings.BING_SEARCH_API_KEY}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.bing.microsoft.com/v7.0/search",
            params={"q": q, "count": 10},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {"title": r.get("name", ""), "url": r.get("url", ""), "content": r.get("snippet", "")}
        for r in data.get("webPages", {}).get("value", [])
    ]
