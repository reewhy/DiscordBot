"""Ricerca su YouTube Data API v3, con cache (ogni ricerca costa 100 unità di quota)."""
from __future__ import annotations

import html
import time

import aiohttp

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
CACHE_TTL = 60 * 60  # 1 ora


class YouTubeError(Exception):
    pass


class YouTubeSearch:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    async def search(self, session: aiohttp.ClientSession, query: str) -> list[dict]:
        q = query.strip()[:100]
        key = q.lower()

        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]

        if not self.api_key:
            raise YouTubeError("YOUTUBE_API_KEY mancante")

        params = {
            "part": "snippet",
            "type": "video",
            "videoEmbeddable": "true",
            "maxResults": "10",
            "q": f"{q} karaoke",
            "key": self.api_key,
        }
        async with session.get(SEARCH_URL, params=params) as resp:
            if resp.status != 200:
                body = (await resp.text())[:200]
                raise YouTubeError(f"YouTube API {resp.status}: {body}")
            data = await resp.json()

        results = [
            {
                "videoId": it["id"]["videoId"],
                "title": html.unescape(it["snippet"]["title"]),
                "channel": html.unescape(it["snippet"]["channelTitle"]),
            }
            for it in data.get("items", [])
        ]
        self._cache[key] = (time.time(), results)
        return results
