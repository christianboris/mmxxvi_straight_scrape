from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SearXNG Configuration
    searxng_url: str = "http://searxng:8080"

    # Search sources tried in order until max_results unique hits are found:
    # "searxng", "duckduckgo", "startpage", "bing" (headless Firefox) and
    # "brave" (ddgs). Override via SEARCH_SOURCES='["searxng","duckduckgo"]'.
    search_sources: list[str] = [
        "searxng",
        "duckduckgo",
        "startpage",
        "brave",
        "bing",
    ]

    # Ollama Configuration
    ollama_host: str = "http://host.docker.internal:11434"
    ollama_model: str = "gpt-oss:20b"

    # Cache Configuration
    cache_dir: str = "/app/data"
    cache_ttl_search: int = 1800  # 30 minutes
    cache_ttl_content: int = 86400  # 24 hours

    # Playwright Configuration
    playwright_max_contexts: int = 3
    # Recycle the browser after this many contexts have been served, to release
    # memory the long-lived browser process accumulates over time. The recycle
    # happens at a safe checkpoint (no context in flight), so it never aborts an
    # in-progress fetch. Set to 0 to disable recycling.
    playwright_recycle_after: int = 200

    # Known SPA domains that require JS rendering
    spa_domains: list[str] = [
        "medium.com",
        "substack.com",
        "notion.so",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "facebook.com",
        "instagram.com",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
