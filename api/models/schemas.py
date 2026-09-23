from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)
    extract: bool = Field(default=True)
    summarize: bool = Field(default=False)
    bypass_cache: bool = Field(default=False)
    engines: list[str] | None = Field(default=None)
    language: str = Field(default="en")


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    markdown: str | None = None
    summary: str | None = None
    fetched_at: datetime | None = None
    from_cache: bool = False
    engine: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    search_time_ms: int
    extract_time_ms: int | None = None
    summarize_time_ms: int | None = None
    total_results: int


class FetchRequest(BaseModel):
    url: str
    force_js: bool = Field(default=False)
    summarize: bool = Field(default=False)
    bypass_cache: bool = Field(default=False)


class FetchResponse(BaseModel):
    url: str
    canonical_url: str
    markdown: str
    summary: str | None = None
    fetched_at: datetime
    from_cache: bool = False
    content_hash: str
    changed_since_last: bool | None = None


class DiffRequest(BaseModel):
    url: str
    since: datetime | None = None


class DiffResponse(BaseModel):
    url: str
    changed: bool
    previous_hash: str | None = None
    current_hash: str
    last_checked: datetime


class PlaywrightPoolStats(BaseModel):
    max_contexts: int
    recycle_after: int
    contexts_served: int
    recycles_total: int


class HealthResponse(BaseModel):
    status: str
    searxng: bool
    ollama: bool
    playwright_contexts: int
    playwright_pool: PlaywrightPoolStats | None = None
    cache_entries: int | None = None
