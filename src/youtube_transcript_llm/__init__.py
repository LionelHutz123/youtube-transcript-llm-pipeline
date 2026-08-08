"""YouTube transcript ingestion utilities for LLM and RAG workflows."""

from .core import (
    TranscriptDocument,
    TranscriptSegment,
    chunk_transcript,
    extract_video_id,
    fetch_transcript,
)

__all__ = [
    "TranscriptDocument",
    "TranscriptSegment",
    "chunk_transcript",
    "extract_video_id",
    "fetch_transcript",
]

__version__ = "0.1.0"
