from __future__ import annotations

import json
from pathlib import Path

import pytest

import youtube_transcript_llm.cli as cli_module
from youtube_transcript_llm.core import TranscriptDocument, TranscriptSegment
from youtube_transcript_llm.discovery import VideoSearchResult

VIDEO_ID = "dQw4w9WgXcQ"


def test_deduplicate_videos_uses_canonical_video_id() -> None:
    videos = [VIDEO_ID, f"https://youtu.be/{VIDEO_ID}", "bad", "bad"]

    assert cli_module._deduplicate_videos(videos) == [VIDEO_ID, "bad"]


def test_search_fetches_transcript_and_adds_discovery_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = VideoSearchResult(
        video_id=VIDEO_ID,
        title="A useful video",
        channel_id="channel-1",
        channel_title="Example Channel",
        published_at="2026-01-02T03:04:05Z",
        description="Description",
    )
    document = TranscriptDocument(
        VIDEO_ID,
        "English",
        "en",
        True,
        (TranscriptSegment("hello world", 0.0, 1.5),),
    )
    monkeypatch.setenv("YOUTUBE_API_KEY", "secret")
    monkeypatch.setattr(cli_module, "search_videos", lambda *args, **kwargs: [result])
    monkeypatch.setattr(cli_module, "fetch_transcript", lambda *args, **kwargs: document)
    output = tmp_path / "result.jsonl"

    exit_code = cli_module.main(["--search", "python", "--output", str(output)])

    assert exit_code == 0
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["video_id"] == VIDEO_ID
    assert record["title"] == "A useful video"
    assert record["channel_id"] == "channel-1"
    assert record["discovery_query"] == "python"


def test_search_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(["--search", "python"])

    assert exc_info.value.code == 2


def test_failed_overwrite_clears_stale_output(tmp_path: Path) -> None:
    output = tmp_path / "result.jsonl"
    output.write_text("stale data\n", encoding="utf-8")

    exit_code = cli_module.main(["bad", "--output", str(output)])

    assert exit_code == 1
    assert output.read_text(encoding="utf-8") == ""
