import asyncio
import hashlib
import json
import time
from pathlib import Path

import aiosqlite

from config import settings


class Cache:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or f"{settings.cache_dir}/cache.db"
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                query_hash TEXT PRIMARY KEY,
                results TEXT,
                created_at REAL,
                expires_at REAL
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS content_cache (
                url_hash TEXT PRIMARY KEY,
                canonical_url TEXT,
                markdown TEXT,
                content_hash TEXT,
                fetched_at REAL,
                expires_at REAL
            )
        """)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def hash_query(
        query: str,
        engines: list[str] | None = None,
        language: str = "en",
        max_results: int = 5,
        extract: bool = True,
        summarize: bool = False,
    ) -> str:
        # Every parameter that shapes the result set belongs in the key, otherwise
        # a request would be served the response of a differently shaped one.
        key = json.dumps(
            {
                "query": query,
                "engines": sorted(engines) if engines else None,
                "language": language,
                "max_results": max_results,
                "extract": extract,
                "summarize": summarize,
            },
            sort_keys=True,
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def get_search(
        self,
        query: str,
        engines: list[str] | None = None,
        language: str = "en",
        max_results: int = 5,
        extract: bool = True,
        summarize: bool = False,
    ) -> list[dict] | None:
        if not self._db:
            return None

        query_hash = self.hash_query(
            query, engines, language, max_results, extract, summarize
        )
        now = time.time()

        async with self._lock:
            cursor = await self._db.execute(
                "SELECT results FROM search_cache WHERE query_hash = ? AND expires_at > ?",
                (query_hash, now)
            )
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    async def set_search(
        self,
        query: str,
        results: list[dict],
        engines: list[str] | None = None,
        language: str = "en",
        max_results: int = 5,
        extract: bool = True,
        summarize: bool = False,
        ttl: int | None = None
    ) -> None:
        if not self._db:
            return

        query_hash = self.hash_query(
            query, engines, language, max_results, extract, summarize
        )
        now = time.time()
        ttl = ttl or settings.cache_ttl_search

        async with self._lock:
            await self._db.execute(
                """INSERT OR REPLACE INTO search_cache
                   (query_hash, results, created_at, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (query_hash, json.dumps(results), now, now + ttl)
            )
            await self._db.commit()

    async def get_content(self, url: str) -> dict | None:
        if not self._db:
            return None

        url_hash = self.hash_url(url)
        now = time.time()

        async with self._lock:
            cursor = await self._db.execute(
                """SELECT canonical_url, markdown, content_hash, fetched_at
                   FROM content_cache
                   WHERE url_hash = ? AND expires_at > ?""",
                (url_hash, now)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "canonical_url": row[0],
                    "markdown": row[1],
                    "content_hash": row[2],
                    "fetched_at": row[3],
                    "from_cache": True
                }
        return None

    async def set_content(
        self,
        url: str,
        canonical_url: str,
        markdown: str,
        ttl: int | None = None
    ) -> None:
        if not self._db:
            return

        url_hash = self.hash_url(url)
        content_hash = self.hash_content(markdown)
        now = time.time()
        ttl = ttl or settings.cache_ttl_content

        async with self._lock:
            await self._db.execute(
                """INSERT OR REPLACE INTO content_cache
                   (url_hash, canonical_url, markdown, content_hash, fetched_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (url_hash, canonical_url, markdown, content_hash, now, now + ttl)
            )
            await self._db.commit()

    async def get_content_hash(self, url: str) -> str | None:
        if not self._db:
            return None

        url_hash = self.hash_url(url)

        async with self._lock:
            cursor = await self._db.execute(
                "SELECT content_hash FROM content_cache WHERE url_hash = ?",
                (url_hash,)
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
        return None

    async def invalidate_search(
        self,
        query: str,
        engines: list[str] | None = None,
        language: str = "en",
        max_results: int = 5,
        extract: bool = True,
        summarize: bool = False,
    ) -> None:
        if not self._db:
            return

        query_hash = self.hash_query(
            query, engines, language, max_results, extract, summarize
        )

        async with self._lock:
            await self._db.execute(
                "DELETE FROM search_cache WHERE query_hash = ?",
                (query_hash,)
            )
            await self._db.commit()

    async def invalidate_content(self, url: str) -> None:
        if not self._db:
            return

        url_hash = self.hash_url(url)

        async with self._lock:
            await self._db.execute(
                "DELETE FROM content_cache WHERE url_hash = ?",
                (url_hash,)
            )
            await self._db.commit()

    async def cleanup_expired(self) -> int:
        if not self._db:
            return 0

        now = time.time()
        deleted = 0

        async with self._lock:
            cursor = await self._db.execute(
                "DELETE FROM search_cache WHERE expires_at < ?", (now,)
            )
            deleted += cursor.rowcount

            cursor = await self._db.execute(
                "DELETE FROM content_cache WHERE expires_at < ?", (now,)
            )
            deleted += cursor.rowcount

            await self._db.commit()

        return deleted


# Global cache instance
cache = Cache()
