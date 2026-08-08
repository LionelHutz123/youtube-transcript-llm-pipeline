from __future__ import annotations

from typing import Any

import pytest
import requests

from youtube_transcript_llm.discovery import VideoDiscoveryError, search_videos

VIDEO_ID = "dQw4w9WgXcQ"


class FakeResponse:
    def __init__(self, payload: dict[str, Any], *, error: bool = False) -> None:
        self.payload = payload
        self.error = error
        self.text = ""

    def raise_for_status(self) -> None:
        if self.error:
            raise requests.HTTPError(response=self)

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeHttp:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.params: dict[str, object] = {}
        self.headers: dict[str, str] = {}
        self.timeout = 0.0

    def get(
        self,
        url: str,
        *,
        params: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        assert url == "https://www.googleapis.com/youtube/v3/search"
        self.params = params
        self.headers = headers
        self.timeout = timeout
        return self.response


def test_search_videos_returns_normalized_results() -> None:
    response = FakeResponse(
        {
            "items": [
                {
                    "id": {"videoId": VIDEO_ID},
                    "snippet": {
                        "title": "A useful &amp; current video",
                        "description": "Description",
                        "channelId": "channel-1",
                        "channelTitle": "Example Channel",
                        "publishedAt": "2026-01-02T03:04:05Z",
                    },
                },
                {"id": {}, "snippet": {}},
            ]
        }
    )
    http = FakeHttp(response)

    results = search_videos(
        "python tutorials",
        api_key="secret",
        max_results=10,
        channel_id="channel-1",
        order="date",
        published_after="2026-01-01T00:00:00Z",
        http=http,
    )

    assert len(results) == 1
    assert results[0].video_id == VIDEO_ID
    assert results[0].title == "A useful & current video"
    assert results[0].source_url.endswith(VIDEO_ID)
    assert results[0].channel_title == "Example Channel"
    assert http.params["type"] == "video"
    assert http.params["channelId"] == "channel-1"
    assert http.params["publishedAfter"] == "2026-01-01T00:00:00Z"
    assert "key" not in http.params
    assert http.headers == {"X-Goog-Api-Key": "secret"}
    assert http.timeout == 20.0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"query": "", "api_key": "key"}, "query"),
        ({"query": "query", "api_key": ""}, "api_key"),
        ({"query": "query", "api_key": "key", "max_results": 51}, "max_results"),
        ({"query": "query", "api_key": "key", "order": "random"}, "order"),
        ({"query": "query", "api_key": "key", "request_timeout": 0}, "request_timeout"),
    ],
)
def test_search_videos_validates_inputs(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        search_videos(**kwargs)


def test_search_videos_surfaces_api_error_message() -> None:
    http = FakeHttp(FakeResponse({"error": {"message": "quota exceeded"}}, error=True))

    with pytest.raises(VideoDiscoveryError, match="quota exceeded"):
        search_videos("query", api_key="key", http=http)
