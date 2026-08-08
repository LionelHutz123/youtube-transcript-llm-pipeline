"""YouTube transcript ingestion utilities for LLM and RAG workflows."""

from .core import (
    TranscriptDocument,
    TranscriptSegment,
    chunk_transcript,
    extract_video_id,
    fetch_transcript,
)
from .discovery import VideoDiscoveryError, VideoSearchResult, search_videos

__all__ = [
    "TranscriptDocument",
    "TranscriptSegment",
    "chunk_transcript",
    "extract_video_id",
    "fetch_transcript",
    "VideoDiscoveryError",
    "VideoSearchResult",
    "search_videos",
]

__version__ = "0.2.0"
