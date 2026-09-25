"""Web search through the `ddgs` library (formerly `duckduckgo_search`).

ddgs impersonates a browser's TLS fingerprint, which Brave accepts while it
rejects SearXNG's plain HTTP client and headless browsers.
"""
import asyncio

from ddgs import DDGS

from services.browser_search import split_language


class DdgsSearch:
    engines = ("brave",)

    async def search(
        self,
        engine: str,
        query: str,
        max_results: int = 10,
        language: str = "en",
    ) -> list[dict]:
        lang, region = split_language(language)
        # ddgs is synchronous; keep it off the event loop.
        items = await asyncio.to_thread(
            DDGS().text,
            query,
            region=f"{region.lower()}-{lang}",
            max_results=max_results,
            backend=engine,
        )
        return [
            {
                "url": item.get("href", ""),
                "title": item.get("title", ""),
                "snippet": item.get("body", ""),
                "engine": engine,
            }
            for item in items
            if item.get("href")
        ]


ddgs_search = DdgsSearch()
