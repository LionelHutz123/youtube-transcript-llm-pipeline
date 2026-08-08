"""Core transcript retrieval and chunking logic."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
}


@dataclass(frozen=True)
class TranscriptSegment:
    """One caption segment with timing information."""

    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class TranscriptDocument:
    """A normalized transcript and its source metadata."""

    video_id: str
    language: str
    language_code: str
    is_generated: bool
    segments: tuple[TranscriptSegment, ...]

    @property
    def source_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def extract_video_id(video: str) -> str:
    """Return an 11-character YouTube video ID from an ID or common URL form."""

    value = video.strip()
    if VIDEO_ID_PATTERN.fullmatch(value):
        return value

    candidate = value if "://" in value else f"https://{value}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        raise ValueError(f"Not a recognized YouTube URL or video ID: {video!r}")

    possible_id: str | None = None
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "youtu.be" and path_parts:
        possible_id = path_parts[0]
    elif parsed.path.rstrip("/") == "/watch":
        possible_id = parse_qs(parsed.query).get("v", [None])[0]
    elif len(path_parts) >= 2 and path_parts[0] in {"embed", "live", "shorts"}:
        possible_id = path_parts[1]

    if possible_id and VIDEO_ID_PATTERN.fullmatch(possible_id):
        return possible_id

    raise ValueError(f"Could not extract a YouTube video ID from: {video!r}")


def fetch_transcript(
    video: str,
    languages: Sequence[str] = ("en",),
    *,
    preserve_formatting: bool = False,
    api: Any | None = None,
) -> TranscriptDocument:
    """Fetch and normalize captions for one YouTube video."""

    video_id = extract_video_id(video)
    client = api or YouTubeTranscriptApi()
    fetched = client.fetch(
        video_id,
        languages=list(languages),
        preserve_formatting=preserve_formatting,
    )

    segments = tuple(
        TranscriptSegment(
            text=snippet.text.strip(),
            start=float(snippet.start),
            duration=float(snippet.duration),
        )
        for snippet in fetched
        if snippet.text.strip()
    )

    return TranscriptDocument(
        video_id=fetched.video_id,
        language=fetched.language,
        language_code=fetched.language_code,
        is_generated=bool(fetched.is_generated),
        segments=segments,
    )


def _text_length(segments: Iterable[TranscriptSegment]) -> int:
    return sum(len(segment.text) + 1 for segment in segments)


def _overlap_tail(
    segments: Sequence[TranscriptSegment], overlap_chars: int
) -> list[TranscriptSegment]:
    if overlap_chars == 0:
        return []

    selected: list[TranscriptSegment] = []
    used = 0
    for segment in reversed(segments):
        cost = len(segment.text) + 1
        if used + cost > overlap_chars:
            break
        selected.insert(0, segment)
        used += cost
    return selected


def chunk_transcript(
    document: TranscriptDocument,
    *,
    max_chars: int = 6_000,
    overlap_chars: int = 500,
) -> list[dict[str, object]]:
    """Split a transcript into timestamped JSON-serializable records for LLM ingestion."""

    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")
    if not document.segments:
        return []

    groups: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []

    for segment in document.segments:
        segment_cost = len(segment.text) + 1
        if current and _text_length(current) + segment_cost > max_chars:
            groups.append(current)
            current = _overlap_tail(current, overlap_chars)
            if current and _text_length(current) + segment_cost > max_chars:
                current = []
        current.append(segment)

    if current:
        groups.append(current)

    records: list[dict[str, object]] = []
    for index, group in enumerate(groups):
        start = group[0].start
        end = max(segment.end for segment in group)
        records.append(
            {
                "schema_version": 1,
                "record_type": "youtube_transcript_chunk",
                "chunk_id": f"youtube:{document.video_id}:{index}",
                "video_id": document.video_id,
                "source_url": document.source_url,
                "language": document.language,
                "language_code": document.language_code,
                "is_generated": document.is_generated,
                "chunk_index": index,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "segment_count": len(group),
                "text": " ".join(segment.text for segment in group),
            }
        )
    return records
