"""YouTube video discovery through the official YouTube Data API."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from typing import Any

import requests

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
SEARCH_ORDERS = frozenset({"date", "rating", "relevance", "title", "viewCount"})


class VideoDiscoveryError(RuntimeError):
    """Raised when YouTube video discovery cannot be completed."""


@dataclass(frozen=True)
class VideoSearchResult:
    """Metadata returned for one discovered YouTube video."""

    video_id: str
    title: str
    channel_id: str
    channel_title: str
    published_at: str
    description: str

    @property
    def source_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def _api_error_message(response: Any) -> str:
    try:
        payload = response.json()
    except (AttributeError, TypeError, ValueError):
        return str(getattr(response, "text", "")).strip()

    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return ""


def search_videos(
    query: str,
    *,
    api_key: str,
    max_results: int = 5,
    channel_id: str | None = None,
    order: str = "relevance",
    published_after: str | None = None,
    request_timeout: float = 20.0,
    http: Any | None = None,
) -> list[VideoSearchResult]:
    """Find public YouTube videos by query using the official Data API v3."""

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if not api_key.strip():
        raise ValueError("api_key must not be empty")
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be between 1 and 50")
    if order not in SEARCH_ORDERS:
        choices = ", ".join(sorted(SEARCH_ORDERS))
        raise ValueError(f"order must be one of: {choices}")
    if request_timeout <= 0:
        raise ValueError("request_timeout must be greater than zero")

    params = {
        "part": "snippet",
        "type": "video",
        "q": normalized_query,
        "maxResults": max_results,
        "order": order,
        "fields": (
            "items(id/videoId,snippet(title,description,channelId,channelTitle,publishedAt))"
        ),
    }
    headers = {"X-Goog-Api-Key": api_key}
    if channel_id:
        params["channelId"] = channel_id
    if published_after:
        params["publishedAfter"] = published_after

    client = http or requests
    try:
        response = client.get(
            YOUTUBE_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=request_timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        detail = _api_error_message(getattr(exc, "response", None))
        suffix = f": {detail}" if detail else ""
        raise VideoDiscoveryError(f"YouTube search request failed{suffix}") from exc
    except (TypeError, ValueError) as exc:
        raise VideoDiscoveryError("YouTube search returned invalid JSON") from exc

    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        raise VideoDiscoveryError("YouTube search returned an invalid response structure")
    results: list[VideoSearchResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id or not isinstance(snippet, dict):
            continue
        results.append(
            VideoSearchResult(
                video_id=str(video_id),
                title=unescape(str(snippet.get("title", ""))),
                channel_id=str(snippet.get("channelId", "")),
                channel_title=unescape(str(snippet.get("channelTitle", ""))),
                published_at=str(snippet.get("publishedAt", "")),
                description=unescape(str(snippet.get("description", ""))),
            )
        )
    return results
