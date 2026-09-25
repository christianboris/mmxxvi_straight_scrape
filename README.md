# mmxxvi_straight_scrape

![](straightscrape.png)

A self-hosted web research and content extraction API. Search the web via SearXNG plus headless-browser and ddgs fallbacks, fetch and render pages (including JS-heavy SPAs), extract clean markdown content, and optionally summarize with Ollama.

## Quick Start

```bash
# Copy environment file
cp dotenv.example .env

# Start all services
docker compose up -d

# Access the WebUI
open http://localhost:9811
```

## Services

| Service  | Port | Description |
|----------|------|-------------|
| API      | 9811 | FastAPI backend + WebUI |
| SearXNG  | 9810 | Metasearch engine |
| MCP      | 9812 | Model Context Protocol server |

## API Endpoints

### POST /api/search

Search the web and extract content from results.

```json
{
  "query": "your search query",
  "max_results": 5,
  "extract": true,
  "summarize": false,
  "bypass_cache": false
}
```

### POST /api/fetch

Fetch a specific URL and extract its content.

```json
{
  "url": "https://example.com/article",
  "force_js": false,
  "summarize": false,
  "bypass_cache": false
}
```

### POST /api/diff

Check if a page has changed since last fetch.

```json
{
  "url": "https://example.com/article"
}
```

### GET /api/health

Service health check.

## MCP Tools

The MCP server exposes these tools:

- `web_search` - Search and extract web content
- `fetch_page` - Fetch a specific URL
- `check_page_changed` - Check if content has changed
- `get_health` - Get service health status

### MCP Configuration

```json
{
  "mcpServers": {
    "web-scrape": {
      "url": "http://localhost:9812/mcp"
    }
  }
}
```

## Configuration

Environment variables (see `dotenv.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_PORT` | 9810 | SearXNG port |
| `API_PORT` | 9811 | API port |
| `MCP_PORT` | 9812 | MCP server port |
| `OLLAMA_HOST` | http://host.docker.internal:11434 | Ollama server URL |
| `OLLAMA_MODEL` | gpt-oss:20b | Model for summarization |
| `CACHE_TTL_SEARCH` | 1800 | Search cache TTL (seconds) |
| `CACHE_TTL_CONTENT` | 86400 | Content cache TTL (seconds) |
| `PLAYWRIGHT_MAX_CONTEXTS` | 3 | Max concurrent browser contexts |
| `SEARCH_SOURCES` | `["searxng","duckduckgo","startpage","brave","bing"]` | Search sources, tried in order until enough unique results are found |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   WebUI     │────▶│   FastAPI   │────▶│   SearXNG   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
┌─────────────┐            │
│  MCP Client │────▶│      │
└─────────────┘     │      ▼
                    │  ┌──────────────┐
                    │  │  Fetch Layer │
                    │  │  ┌─────────┐ │
                    │  │  │  httpx  │ │◀─── Fast path
                    │  │  └─────────┘ │
                    │  │  ┌─────────┐ │
                    │  │  │Playwright│◀─── JS render path
                    │  │  └─────────┘ │
                    │  └──────┬───────┘
                    │         │
                    │         ▼
                    │  ┌──────────────┐
                    │  │  Extractor   │
                    │  │ (Trafilatura)│
                    │  └──────┬───────┘
                    │         │
                    │         ▼
                    │  ┌──────────────┐     ┌─────────────┐
                    └─▶│    Cache     │     │   Ollama    │
                       │   (SQLite)   │     │ (summarize) │
                       └──────────────┘     └─────────────┘
```

## Tech Stack

- **API**: FastAPI, httpx, Playwright, Trafilatura
- **Search**: SearXNG (Google CSE, Bing, Wikipedia); DuckDuckGo, Startpage and Bing via headless Firefox; Brave via [ddgs](https://pypi.org/project/ddgs/)
- **Extraction**: Trafilatura + readability-lxml fallback
- **Cache**: SQLite
- **Summarization**: Ollama
- **MCP**: FastMCP
