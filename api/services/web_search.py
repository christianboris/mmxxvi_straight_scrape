"""Search across several sources in turn until enough unique results are found.

Sources:
  searxng     SearXNG with the engines that still answer it (Google CSE, Bing)
  duckduckgo  headless Firefox (services.browser_search)
  startpage   headless Firefox
  bing        headless Firefox
  brave       ddgs library (services.ddgs_search)

Each source is best-effort: a failing or blocked source is recorded in the
returned error map and the next one is tried.
"""
import logging
from urllib.parse import urlparse, urlunparse

from config import settings
from services.browser_search import browser_search
from services.ddgs_search import ddgs_search
from services.searxng import searxng_client

logger = logging.getLogger(__name__)

NATIVE_SOURCES = {
    **{name: browser_search for name in browser_search.engines},
    **{name: ddgs_search for name in ddgs_search.engines},
}
SEARXNG = "searxng"


def normalize_url(url: str) -> str:
    """Key for de-duplication: case-insensitive host, no fragment or trailing slash."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), host, path, "", parsed.query, ""))


def plan_sources(engines: list[str] | None) -> list[tuple[str, list[str] | None]]:
    """Ordered (source, searxng_engines) pairs to try.

    Without `engines` the configured default order is used. With `engines`,
    names of native sources run natively (in the given order) and every other
    name is handed to SearXNG as one combined engine list.
    """
    if not engines:
        return [(source, None) for source in settings.search_sources]

    plan: list[tuple[str, list[str] | None]] = []
    searxng_engines: list[str] = []
    for name in engines:
        if name in NATIVE_SOURCES:
            plan.append((name, None))
        elif name == SEARXNG:
            continue  # SearXNG with its own default engines, added below
        else:
            searxng_engines.append(name)
    if searxng_engines:
        plan.insert(0, (SEARXNG, searxng_engines))
    elif SEARXNG in engines:
        plan.insert(0, (SEARXNG, None))
    return plan


async def _query_source(
    source: str,
    query: str,
    max_results: int,
    language: str,
    searxng_engines: list[str] | None,
) -> list[dict]:
    if source == SEARXNG:
        return await searxng_client.search(
            query=query,
            max_results=max_results,
            engines=searxng_engines,
            language=language,
        )
    return await NATIVE_SOURCES[source].search(
        source, query, max_results=max_results, language=language
    )


async def search(
    query: str,
    max_results: int = 10,
    engines: list[str] | None = None,
    language: str = "en",
) -> tuple[list[dict], dict[str, str]]:
    """Return (results, errors); errors maps source name -> failure message."""
    results: list[dict] = []
    seen: set[str] = set()
    errors: dict[str, str] = {}

    for source, searxng_engines in plan_sources(engines):
        if len(results) >= max_results:
            break
        if source != SEARXNG and source not in NATIVE_SOURCES:
            errors[source] = "unknown search source"
            continue
        try:
            hits = await _query_source(
                source, query, max_results, language, searxng_engines
            )
        except Exception as e:
            logger.warning("search source %s failed: %s", source, e)
            errors[source] = str(e) or type(e).__name__
            continue

        for hit in hits:
            key = normalize_url(hit["url"])
            if key in seen:
                continue
            seen.add(key)
            results.append(hit)
            if len(results) >= max_results:
                break

    return results, errors
