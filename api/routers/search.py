import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from cache import cache
from models.schemas import SearchRequest, SearchResult, SearchResponse
from services import web_search
from services.fetcher import fetcher
from services.extractor import extract_content
from services.summarizer import summarizer

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    start_time = time.time()

    cache_key_params = {
        "engines": request.engines,
        "language": request.language,
        "max_results": request.max_results,
        "extract": request.extract,
        "summarize": request.summarize,
    }

    if not request.bypass_cache:
        cached_results = await cache.get_search(request.query, **cache_key_params)
        if cached_results:
            search_time_ms = int((time.time() - start_time) * 1000)
            results = [SearchResult(**r) for r in cached_results]
            return SearchResponse(
                query=request.query,
                results=results,
                search_time_ms=search_time_ms,
                total_results=len(results),
            )

    search_results, source_errors = await web_search.search(
        query=request.query,
        max_results=request.max_results,
        engines=request.engines,
        language=request.language,
    )
    if not search_results and source_errors:
        detail = "; ".join(f"{src}: {err}" for src, err in source_errors.items())
        raise HTTPException(status_code=503, detail=f"Search failed: {detail}")

    search_time_ms = int((time.time() - start_time) * 1000)

    results: list[SearchResult] = []
    for item in search_results:
        results.append(SearchResult(
            url=item["url"],
            title=item["title"],
            snippet=item["snippet"],
            engine=item.get("engine"),
        ))

    extract_time_ms = None
    summarize_time_ms = None

    if request.extract and results:
        extract_start = time.time()

        async def fetch_and_extract(result: SearchResult) -> SearchResult:
            cached = await cache.get_content(result.url)
            if cached and not request.bypass_cache:
                result.markdown = cached["markdown"]
                result.fetched_at = datetime.fromtimestamp(
                    cached["fetched_at"], tz=timezone.utc
                )
                result.from_cache = True
                return result

            html, canonical_url = await fetcher.fetch(result.url)
            if html:
                markdown = extract_content(html, result.url)
                result.markdown = markdown
                result.fetched_at = datetime.now(timezone.utc)

                await cache.set_content(result.url, canonical_url, markdown)
            return result

        results = await asyncio.gather(*[fetch_and_extract(r) for r in results])
        results = list(results)
        extract_time_ms = int((time.time() - extract_start) * 1000)

    if request.summarize and results:
        summarize_start = time.time()

        async def add_summary(result: SearchResult) -> SearchResult:
            if result.markdown:
                result.summary = await summarizer.summarize(
                    result.markdown,
                    focus=request.query
                )
            return result

        results = await asyncio.gather(*[add_summary(r) for r in results])
        results = list(results)
        summarize_time_ms = int((time.time() - summarize_start) * 1000)

    if results:
        results_dicts = [r.model_dump(mode="json") for r in results]
        await cache.set_search(request.query, results_dicts, **cache_key_params)

    return SearchResponse(
        query=request.query,
        results=results,
        search_time_ms=search_time_ms,
        extract_time_ms=extract_time_ms,
        summarize_time_ms=summarize_time_ms,
        total_results=len(results),
        source_errors=source_errors or None,
    )
