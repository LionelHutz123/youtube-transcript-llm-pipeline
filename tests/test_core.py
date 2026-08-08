from __future__ import annotations

from dataclasses import dataclass

import pytest

from youtube_transcript_llm.core import (
    TranscriptDocument,
    TranscriptSegment,
    chunk_transcript,
    extract_video_id,
    fetch_transcript,
)

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "value",
    [
        VIDEO_ID,
        f"https://www.youtube.com/watch?v={VIDEO_ID}&feature=share",
        f"https://youtu.be/{VIDEO_ID}?si=example",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://www.youtube.com/embed/{VIDEO_ID}",
        f"https://www.youtube.com/v/{VIDEO_ID}",
        f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
        f"youtube.com/live/{VIDEO_ID}",
        f"//youtu.be/{VIDEO_ID}",
    ],
)
def test_extract_video_id(value: str) -> None:
    assert extract_video_id(value) == VIDEO_ID


@pytest.mark.parametrize("value", ["", "not a video", "https://example.com/watch?v=123"])
def test_extract_video_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        extract_video_id(value)


def test_chunk_transcript_preserves_timestamps_and_overlap() -> None:
    document = TranscriptDocument(
        video_id=VIDEO_ID,
        language="English",
        language_code="en",
        is_generated=True,
        segments=(
            TranscriptSegment("alpha", 0.0, 1.0),
            TranscriptSegment("bravo", 1.0, 1.0),
            TranscriptSegment("charlie", 2.0, 1.0),
            TranscriptSegment("delta", 3.0, 1.0),
        ),
    )

    records = chunk_transcript(document, max_chars=20, overlap_chars=8)

    assert len(records) == 2
    assert records[0]["text"] == "alpha bravo charlie"
    assert records[1]["text"] == "charlie delta"
    assert records[0]["start_seconds"] == 0.0
    assert records[0]["end_seconds"] == 3.0
    assert records[1]["chunk_id"] == f"youtube:{VIDEO_ID}:1"


def test_chunk_transcript_validates_limits() -> None:
    document = TranscriptDocument(VIDEO_ID, "English", "en", False, ())
    with pytest.raises(ValueError):
        chunk_transcript(document, max_chars=0)
    with pytest.raises(ValueError):
        chunk_transcript(document, max_chars=100, overlap_chars=100)


@dataclass
class FakeSnippet:
    text: str
    start: float
    duration: float


class FakeFetched(list[FakeSnippet]):
    video_id = VIDEO_ID
    language = "English"
    language_code = "en"
    is_generated = False


class FakeApi:
    def fetch(self, video_id: str, **kwargs: object) -> FakeFetched:
        assert video_id == VIDEO_ID
        assert kwargs["languages"] == ["en"]
        return FakeFetched([FakeSnippet(" hello ", 0.0, 1.5), FakeSnippet("", 1.5, 0.5)])


def test_fetch_transcript_normalizes_api_response() -> None:
    document = fetch_transcript(VIDEO_ID, api=FakeApi())
    assert document.video_id == VIDEO_ID
    assert document.segments == (TranscriptSegment("hello", 0.0, 1.5),)


def test_fetch_transcript_validates_network_options() -> None:
    with pytest.raises(ValueError, match="languages"):
        fetch_transcript(VIDEO_ID, languages=(), api=FakeApi())
    with pytest.raises(ValueError, match="request_timeout"):
        fetch_transcript(VIDEO_ID, request_timeout=0, api=FakeApi())
    with pytest.raises(ValueError, match="max_retries"):
        fetch_transcript(VIDEO_ID, max_retries=-1, api=FakeApi())
