"""Web search by driving a real (headless) Firefox through the shared Playwright pool.

DuckDuckGo, Startpage and Bing block plain HTTP clients such as SearXNG's
(CAPTCHA / 429 on the very first request) but serve a real browser normally.
Google and Brave detect headless browsers as well, so they are not offered here.
"""
import base64
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, urlparse

from services.fetcher import fetcher


class SearchBlockedError(Exception):
    """The engine answered with a CAPTCHA / bot challenge instead of results."""


@dataclass(frozen=True)
class EngineSpec:
    url: str             # search URL template: {q} query, {lang}/{region} locale parts
    result: str          # CSS selector of one result container
    link: str            # selector (inside result) of the title link
    snippet: str         # selector (inside result) of the snippet text
    blocked_markers: tuple[str, ...]  # substrings of page URL / HTML meaning "blocked"


ENGINES: dict[str, EngineSpec] = {
    "duckduckgo": EngineSpec(
        url="https://duckduckgo.com/?q={q}&kl={region_lower}-{lang}",
        result="article[data-testid=result]",
        link="a[data-testid=result-title-a]",
        snippet="[data-result=snippet]",
        blocked_markers=("anomaly-modal", "challenge-form"),
    ),
    "startpage": EngineSpec(
        url="https://www.startpage.com/sp/search?query={q}&lui={lang}",
        result="div.result",
        link="a.result-title",
        snippet="p.description",
        blocked_markers=("/sp/captcha",),
    ),
    "bing": EngineSpec(
        url="https://www.bing.com/search?q={q}&setlang={lang}&cc={region}",
        result="li.b_algo",
        link="h2 a",
        snippet=".b_caption p",
        blocked_markers=("/turing/captcha", "b_captcha"),
    ),
}

# Runs in the page: collect {url, title, snippet} from every result container.
_EXTRACT_JS = """
([resultSel, linkSel, snippetSel]) => [...document.querySelectorAll(resultSel)].map(r => {
    const a = r.querySelector(linkSel);
    const s = r.querySelector(snippetSel);
    return {
        url: a ? a.href : "",
        title: a ? a.innerText.trim() : "",
        snippet: s ? s.innerText.trim() : "",
    };
})
"""


def split_language(language: str) -> tuple[str, str]:
    """'de' -> ('de', 'DE'), 'en' -> ('en', 'US'), 'de-AT' -> ('de', 'AT')."""
    lang, _, region = language.replace("_", "-").partition("-")
    lang = lang.lower() if lang and lang not in ("all", "auto") else "en"
    if not region:
        region = "US" if lang == "en" else lang
    return lang, region.upper()


def decode_bing_url(url: str) -> str:
    """Bing wraps result links as bing.com/ck/a?...&u=a1<base64url(target)>."""
    parsed = urlparse(url)
    if not (parsed.netloc.endswith("bing.com") and parsed.path.startswith("/ck/a")):
        return url
    encoded = parse_qs(parsed.query).get("u", [""])[0]
    if not encoded.startswith("a1"):
        return url
    encoded = encoded[2:]
    try:
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return url


class BrowserSearch:
    engines = tuple(ENGINES)

    async def search(
        self,
        engine: str,
        query: str,
        max_results: int = 10,
        language: str = "en",
    ) -> list[dict]:
        spec = ENGINES[engine]
        lang, region = split_language(language)
        url = spec.url.format(
            q=quote_plus(query), lang=lang, region=region, region_lower=region.lower()
        )

        # user_agent=None: keep Firefox's real UA so it matches the TLS fingerprint.
        async with fetcher.browser_context(
            user_agent=None, locale=f"{lang}-{region}"
        ) as context:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(spec.result, timeout=10000)
            except Exception:
                pass  # no results or blocked; decided below
            items = await page.evaluate(
                _EXTRACT_JS, [spec.result, spec.link, spec.snippet]
            )
            if not items:
                html = await page.content()
                if any(m in page.url or m in html for m in spec.blocked_markers):
                    raise SearchBlockedError(f"{engine}: blocked by bot detection")
            await page.close()

        results = []
        for item in items:
            target = decode_bing_url(item["url"]) if engine == "bing" else item["url"]
            if not target.startswith(("http://", "https://")):
                continue
            results.append({
                "url": target,
                "title": item["title"],
                "snippet": item["snippet"],
                "engine": engine,
            })
            if len(results) >= max_results:
                break
        return results


browser_search = BrowserSearch()
