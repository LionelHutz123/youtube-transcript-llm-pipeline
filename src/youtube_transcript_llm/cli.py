"""Command-line interface for producing LLM-ready transcript chunks."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .core import chunk_transcript, fetch_transcript


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-transcript",
        description="Fetch YouTube captions and write timestamped, LLM-ready JSONL chunks.",
    )
    parser.add_argument("videos", nargs="+", help="YouTube video URLs or 11-character IDs")
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records: list[dict[str, object]] = []
    failures = 0

    for video in args.videos:
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
            records.extend(video_records)
            print(
                f"Fetched {document.video_id}: {len(document.segments)} segments, "
                f"{len(video_records)} chunks",
                file=sys.stderr,
            )
        except Exception as exc:  # Keep batch runs moving when one video is unavailable.
            failures += 1
            print(f"Failed {video!r}: {exc}", file=sys.stderr)

    if records:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if args.append else "w"
        with args.output.open(mode, encoding="utf-8", newline="\n") as output_file:
            for record in records:
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"Wrote {len(records)} chunks to {args.output}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
