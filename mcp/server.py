import os
import httpx
from fastmcp import FastMCP

API_URL = os.environ.get("API_URL", "http://api:8000")

mcp = FastMCP("Web Scrape MCP Server")


@mcp.tool()
async def web_search(
    query: str,
    max_results: int = 5,
    extract: bool = True,
    summarize: bool = False,
    bypass_cache: bool = False,
    engines: list[str] | None = None,
    language: str = "en",
) -> dict:
    """
    Search the web and extract content from results.

    Args:
        query: The search query
        max_results: Maximum number of results to return (1-20)
        extract: Whether to fetch and extract markdown content from each result
        summarize: Whether to generate AI summaries of the content
        bypass_cache: Skip cache and fetch fresh results
        engines: Specific search engines to use (e.g., ["duckduckgo", "brave"])
        language: SearXNG language code for the search (e.g., "de", "en", "auto")

    Returns:
        Search results with optional markdown content and summaries
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "query": query,
            "max_results": max_results,
            "extract": extract,
            "summarize": summarize,
            "bypass_cache": bypass_cache,
            "language": language,
        }
        if engines:
            payload["engines"] = engines

        response = await client.post(f"{API_URL}/api/search", json=payload)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def fetch_page(
    url: str,
    force_js: bool = False,
    summarize: bool = False,
    bypass_cache: bool = False,
) -> dict:
    """
    Fetch a specific URL and extract its content as markdown.

    Args:
        url: The URL to fetch
        force_js: Force JavaScript rendering (use for SPAs and dynamic sites)
        summarize: Whether to generate an AI summary of the content
        bypass_cache: Skip cache and fetch fresh content

    Returns:
        Extracted markdown content with metadata
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "url": url,
            "force_js": force_js,
            "summarize": summarize,
            "bypass_cache": bypass_cache,
        }

        response = await client.post(f"{API_URL}/api/fetch", json=payload)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def check_page_changed(
    url: str,
) -> dict:
    """
    Check if a page's content has changed since it was last fetched.

    Args:
        url: The URL to check

    Returns:
        Whether the content changed and the content hashes
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {"url": url}

        response = await client.post(f"{API_URL}/api/diff", json=payload)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_health() -> dict:
    """
    Get the health status of the web scrape service.

    Returns:
        Service health information including SearXNG and Ollama status
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{API_URL}/api/health")
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
