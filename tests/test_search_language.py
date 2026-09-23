"""The search language is selectable per request and part of the cache key."""


async def post_search(client, **overrides) -> dict:
    payload = {"query": "wetter", "max_results": 2, "extract": False}
    payload.update(overrides)
    response = await client.post("/api/search", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def test_language_is_passed_to_searxng(client, searxng):
    await post_search(client, language="de")
    assert searxng.calls[0]["language"] == "de"


async def test_language_defaults_to_english(client, searxng):
    await post_search(client)
    assert searxng.calls[0]["language"] == "en"


async def test_languages_are_cached_separately(client, searxng):
    german = await post_search(client, language="de")
    english = await post_search(client, language="en")

    assert [call["language"] for call in searxng.calls] == ["de", "en"]
    assert german["results"] != english["results"]

    cached = await post_search(client, language="de")
    assert len(searxng.calls) == 2
    assert cached["results"] == german["results"]
