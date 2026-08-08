"""Command-line interface for producing LLM-ready transcript chunks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .core import chunk_transcript, extract_video_id, fetch_transcript
from .discovery import SEARCH_ORDERS, VideoDiscoveryError, VideoSearchResult, search_videos


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-transcript",
        description="Fetch YouTube captions and write timestamped, LLM-ready JSONL chunks.",
    )
    parser.add_argument("videos", nargs="*", help="YouTube video URLs or 11-character IDs")
    parser.add_argument(
        "--search",
        metavar="QUERY",
        help="Discover videos with the YouTube Data API, then fetch their transcripts",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=5,
        metavar="NUMBER",
        help="Maximum discovered videos (default: 5; maximum: 50)",
    )
    parser.add_argument(
        "--search-order",
        choices=sorted(SEARCH_ORDERS),
        default="relevance",
        help="YouTube search result order (default: relevance)",
    )
    parser.add_argument(
        "--channel-id",
        help="Restrict --search to one YouTube channel ID",
    )
    parser.add_argument(
        "--published-after",
        metavar="RFC3339",
        help="Restrict --search to videos published after this RFC 3339 timestamp",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["en"],
        metavar="CODE",
        help="Preferred language codes in priority order (default: en)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/transcripts.jsonl"),
        help="JSONL destination (default: data/transcripts.jsonl)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=6_000,
        help="Approximate maximum characters per chunk (default: 6000)",
    )
    parser.add_argument(
        "--overlap-chars",
        type=int,
        default=500,
        help="Maximum repeated characters between adjacent chunks (default: 500)",
    )
    parser.add_argument("--append", action="store_true", help="Append instead of overwriting")
    parser.add_argument(
        "--preserve-formatting",
        action="store_true",
        help="Preserve supported HTML formatting in caption text",
    )
    return parser


def _deduplicate_videos(videos: Sequence[str]) -> list[str]:
    deduplicated: list[str] = []
    seen: set[str] = set()
    for video in videos:
        try:
            identity = extract_video_id(video)
        except ValueError:
            identity = video
        if identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(video)
    return deduplicated


def _write_jsonl(records: Sequence[dict[str, object]], output: Path, *, append: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with output.open("a", encoding="utf-8", newline="\n") as output_file:
            for record in records:
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            for record in records:
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        temporary_path.replace(output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _search_metadata(result: VideoSearchResult, query: str) -> dict[str, object]:
    return {
        "title": result.title,
        "channel_id": result.channel_id,
        "channel_title": result.channel_title,
        "published_at": result.published_at,
        "discovery_query": query,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.videos and not args.search:
        parser.error("provide at least one VIDEO or use --search QUERY")

    discovered_by_id: dict[str, VideoSearchResult] = {}
    videos = list(args.videos)
    if args.search:
        api_key = os.environ.get("YOUTUBE_API_KEY", "")
        if not api_key:
            parser.error("--search requires the YOUTUBE_API_KEY environment variable")
        try:
            discovered = search_videos(
                args.search,
                api_key=api_key,
                max_results=args.search_limit,
                channel_id=args.channel_id,
                order=args.search_order,
                published_after=args.published_after,
            )
        except (ValueError, VideoDiscoveryError) as exc:
            print(f"Video discovery failed: {exc}", file=sys.stderr)
            return 2
        discovered_by_id = {result.video_id: result for result in discovered}
        videos.extend(discovered_by_id)
        print(f"Discovered {len(discovered)} videos for {args.search!r}", file=sys.stderr)
        for result in discovered:
            print(f"  {result.video_id}  {result.title}", file=sys.stderr)

    videos = _deduplicate_videos(videos)
    records: list[dict[str, object]] = []
    failures = 0

    for video in videos:
        try:
            document = fetch_transcript(
                video,
                languages=args.languages,
                preserve_formatting=args.preserve_formatting,
            )
            video_records = chunk_transcript(
                document,
                max_chars=args.max_chars,
                overlap_chars=args.overlap_chars,
            )
            if not video_records:
                raise RuntimeError("the selected transcript was empty")
            discovered = discovered_by_id.get(document.video_id)
            if discovered is not None:
                metadata = _search_metadata(discovered, args.search)
                for record in video_records:
                    record.update(metadata)
            records.extend(video_records)
            print(
                f"Fetched {document.video_id}: {len(document.segments)} segments, "
                f"{len(video_records)} chunks",
                file=sys.stderr,
            )
        except Exception as exc:  # Keep batch runs moving when one video is unavailable.
            failures += 1
            print(f"Failed {video!r}: {exc}", file=sys.stderr)

    if records or not args.append:
        _write_jsonl(records, args.output, append=args.append)
        print(f"Wrote {len(records)} chunks to {args.output}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
