# YouTube Transcript → LLM Pipeline

Turn one or more YouTube links into clean, timestamped JSONL chunks that are ready for an LLM, embedding model, vector database, or retrieval-augmented generation (RAG) workflow.

The core pipeline is intentionally small:

```text
YouTube URL or video ID
        ↓
Resolve the 11-character video ID
        ↓
Fetch available human or auto-generated captions
        ↓
Normalize text and preserve timestamps
        ↓
Create overlapping, LLM-sized chunks
        ↓
Write provider-neutral JSONL
        ↓
Summarize, classify, embed, search, or add to RAG
```

This project collects captions that are already available for a video. It does **not** download the video or audio. Fetching a known video's transcript does not require an API key. Optional keyword or channel discovery uses the official YouTube Data API and requires a `YOUTUBE_API_KEY`.

## Why this exists

LLMs work with text, not a YouTube watch page. Before a model can summarize a video, answer questions about it, compare it with other videos, or place it in a searchable knowledge base, the spoken content needs to become structured text.

This tool handles that ingestion boundary. It accepts common YouTube URL formats, fetches captions, retains useful source metadata, and creates chunks that can be passed to nearly any downstream AI system.

For organizational adoption, Google Cloud ownership, API-key security, verified live test data, quota planning, compliance considerations, and production architecture, see the [Business Implementation Guide](docs/BUSINESS_IMPLEMENTATION_GUIDE.md).

## Features

- Accepts normal watch URLs, `youtu.be` links, Shorts, embeds, live URLs, or raw video IDs.
- Can discover videos by keyword, channel, date, and result order through the official YouTube Data API.
- Supports language preference order such as English first and Spanish second.
- Works with manually authored and auto-generated captions when YouTube exposes them.
- Preserves start and end timestamps for citation and playback links.
- Produces newline-delimited JSON: one independently processable chunk per line.
- Adds configurable overlap so context is not abruptly lost between chunks.
- Has no LLM-provider dependency; transcript retrieval requires no API key.
- Adds bounded network timeouts and retries for transient transcript failures.
- Writes overwrite-mode JSONL atomically so interrupted runs do not leave partial files.
- Includes tests, linting, and modern Python packaging metadata.

## Quick start

### 1. Install

Python 3.11 or newer is required. Python 3.12 is recommended. Avoid Apple's legacy system Python, which is currently Python 3.9 with an obsolete LibreSSL build.

```bash
git clone https://github.com/LionelHutz123/youtube-transcript-llm-pipeline.git
cd youtube-transcript-llm-pipeline

python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS or Linux
source .venv/bin/activate
```

Upgrade the environment's packaging tools, then install the command:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install .
```

### 2. Fetch a transcript

```bash
yt-transcript "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

By default, the result is written to `data/transcripts.jsonl`.

### 3. Process several videos

```bash
yt-transcript \
  "https://youtu.be/VIDEO_ID_1" \
  "https://www.youtube.com/watch?v=VIDEO_ID_2" \
  --languages en es \
  --output data/my-corpus.jsonl
```

On Windows PowerShell, use a backtick (`` ` ``) instead of `\` for multiline commands, or place the command on one line.

### 4. Discover videos and fetch their transcripts

Discovery is separate from transcript retrieval. Create a Google Cloud project, enable YouTube Data API v3, and place its API key in an environment variable:

```bash
export YOUTUBE_API_KEY="your-api-key"
```

```powershell
$env:YOUTUBE_API_KEY = "your-api-key"
```

Then search YouTube and process the discovered videos in one command:

```bash
yt-transcript \
  --search "retrieval augmented generation tutorial" \
  --search-limit 3 \
  --published-after 2025-01-01T00:00:00Z \
  --output data/rag-videos.jsonl
```

Use `--channel-id CHANNEL_ID` to restrict discovery to one channel. Search results add `title`, `channel_id`, `channel_title`, `published_at`, and `discovery_query` to each transcript chunk.

## Command reference

```text
yt-transcript [VIDEO ...]
  --search QUERY                 Discover videos, then fetch their transcripts
  --search-limit NUMBER          Maximum search results, from 1 to 50
  --search-order ORDER           relevance, date, rating, title, or viewCount
  --channel-id CHANNEL_ID        Restrict search to one channel
  --published-after RFC3339      Restrict search by publication timestamp
  --languages CODE [CODE ...]   Preferred languages in priority order
  --output PATH                 JSONL destination
  --max-chars NUMBER            Approximate maximum characters per chunk
  --overlap-chars NUMBER        Maximum repeated characters between chunks
  --append                      Append to an existing corpus
  --preserve-formatting         Keep supported caption HTML formatting
```

Examples:

```bash
# Prefer a human or generated English transcript, then fall back to Spanish
yt-transcript VIDEO_ID --languages en es

# Create smaller chunks for models with a limited context window
yt-transcript VIDEO_ID --max-chars 3000 --overlap-chars 300

# Build a corpus over multiple runs
yt-transcript VIDEO_ID_1 --output data/corpus.jsonl
yt-transcript VIDEO_ID_2 --output data/corpus.jsonl --append

# Combine a known video with discovered results; duplicate IDs are removed
yt-transcript VIDEO_ID --search "local LLM tutorial" --search-limit 5
```

## Output format

Every JSONL line represents one transcript chunk:

```json
{
  "schema_version": 1,
  "record_type": "youtube_transcript_chunk",
  "chunk_id": "youtube:dQw4w9WgXcQ:0",
  "video_id": "dQw4w9WgXcQ",
  "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "English",
  "language_code": "en",
  "is_generated": false,
  "chunk_index": 0,
  "start_seconds": 0.0,
  "end_seconds": 94.2,
  "segment_count": 31,
  "text": "Transcript text for this chunk..."
}
```

The `source_url`, `video_id`, and timestamps make it possible to preserve citations after the text has been embedded or sent to another service.

## Using the output with an LLM

The output is provider-neutral. Read one line at a time and send the `text` field to your model with the metadata needed by your application:

```python
import json
from pathlib import Path

records = [
    json.loads(line)
    for line in Path("data/transcripts.jsonl").read_text(encoding="utf-8").splitlines()
]

for record in records:
    prompt = f"""
    Summarize this section of a YouTube transcript.
    Source: {record["source_url"]}
    Time range: {record["start_seconds"]}–{record["end_seconds"]} seconds

    {record["text"]}
    """
    # Send `prompt` to the LLM client of your choice.
```

Common next steps include:

- Map/reduce summarization across long videos.
- Topic, sentiment, claim, or entity extraction.
- Embedding each chunk in a vector database.
- Semantic search over a collection of channels or videos.
- RAG with source URLs and timestamps included in answers.
- Comparing how several videos discuss the same subject.

## Use as a Python library

```python
from youtube_transcript_llm import chunk_transcript, fetch_transcript, search_videos

document = fetch_transcript(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    languages=["en"],
)
records = chunk_transcript(document, max_chars=6000, overlap_chars=500)

print(records[0]["text"])
```

Programmatically discover videos and feed their IDs into the same retrieval path:

```python
import os

from youtube_transcript_llm import chunk_transcript, fetch_transcript, search_videos

matches = search_videos(
    "retrieval augmented generation tutorial",
    api_key=os.environ["YOUTUBE_API_KEY"],
    max_results=5,
    order="date",
)

for match in matches:
    try:
        document = fetch_transcript(match.video_id, languages=["en", "es"])
    except Exception as exc:
        # A discovered video may be private, blocked, or have no matching captions.
        print(f"Skipping {match.video_id}: {exc}")
        continue

    for record in chunk_transcript(document):
        print(match.title, record["start_seconds"], record["text"][:80])
```

Keep the discovery metadata alongside the transcript records in a real application. A search result only proves that a video exists; caption availability is a separate property and must be checked per video.

## Development

Install development tools and run the checks:

```bash
python -m pip install ".[dev]"
ruff check .
pytest
```

The test suite does not make live YouTube requests. It tests URL parsing, transcript normalization, discovery responses and failures, CLI output safety, metadata, chunk boundaries, and overlap deterministically.

## Project structure

```text
.
├── .env.example
├── .github/workflows/ci.yml
├── CHANGELOG.md
├── data/
├── docs/BUSINESS_IMPLEMENTATION_GUIDE.md
├── src/youtube_transcript_llm/
│   ├── __init__.py
│   ├── cli.py
│   ├── core.py
│   └── discovery.py
├── tests/
├── pyproject.toml
└── README.md
```

## Limitations

- A video must expose captions or a transcript. This project does not perform speech-to-text on videos without captions.
- Private, deleted, region-locked, and some age-restricted videos may be unavailable.
- YouTube can rate-limit or block automated transcript requests, especially from cloud-provider IP addresses.
- Generic video discovery requires a YouTube Data API v3 key and consumes Google API quota. Direct transcript retrieval remains keyless.
- Playlist enumeration and exhaustive channel-upload enumeration are outside the current scope. Search can be restricted to a channel, but it is still a relevance/date-based search.
- The underlying library uses an undocumented YouTube web endpoint, so upstream changes can temporarily break retrieval.

## Responsible use

Use the project only for videos and transcripts you are permitted to process. Respect copyright, privacy, YouTube's terms, applicable law, and reasonable request rates. Do not treat generated captions as authoritative: they can contain transcription errors, especially for names, numbers, and specialized terminology.

## License

MIT. See [LICENSE](LICENSE).
