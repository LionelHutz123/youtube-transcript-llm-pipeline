# Business Implementation Guide

This guide explains how an organization can adapt this project to find public YouTube videos, retrieve available captions, and prepare timestamped text for analysis, search, summarization, or retrieval-augmented generation (RAG).

It separates two capabilities that have different authentication and reliability characteristics:

1. **Video discovery** uses the official YouTube Data API v3 and a Google Cloud API key.
2. **Transcript retrieval** uses the open-source `youtube-transcript-api` package to access captions exposed by YouTube's web client. It does not require a Google account or API key, but it relies on an undocumented endpoint.

This is an engineering guide, not legal advice. Every business should review YouTube's terms, its own content rights, privacy obligations, and the rules applicable to its industry and location.

## Executive verdict

As of August 8, 2026, the pipeline can:

- Resolve common YouTube URLs and raw 11-character IDs.
- Search for public videos by keyword through Google's supported API.
- Restrict searches by channel, publication date, and result order.
- Retrieve both manually authored and auto-generated captions when YouTube exposes them.
- Preserve source URLs, language, generated/manual status, and time ranges.
- Split long transcripts into overlapping JSONL records for downstream processing.
- Continue batch processing when an individual video lacks a usable transcript.

Discovery does **not** guarantee transcript availability. A video can appear in search while its captions are disabled, missing in the requested language, private, region-restricted, age-restricted, or temporarily inaccessible.

## Verified test data

The following public videos were used as live smoke tests. Transcript text is intentionally not committed to the repository.

| Video | Caption type observed | Segments retrieved | Duration represented | Result |
| --- | --- | ---: | ---: | --- |
| `dQw4w9WgXcQ` | Manually authored English | 61 | 1.36–211.32 seconds | Successful |
| `YZkyL-f-YXY` | Auto-generated English | 139 | 1.64–322.08 seconds | Successful |

Additional verification:

- A `youtube-nocookie.com/embed/dQw4w9WgXcQ` URL resolved to the correct canonical ID.
- With `max_chars=750` and `overlap_chars=100`, the first video produced four chunks; the largest contained 736 characters.
- With `max_chars=1000` and `overlap_chars=150`, the auto-generated transcript produced seven chunks; the largest contained 995 characters.
- Google rejected a deliberately invalid API key with a clean, structured error, confirming that the discovery request reached the official endpoint without creating an output file.
- The deterministic suite contains 27 tests covering URL resolution, normalization, discovery payloads and failures, CLI behavior, chunking, and output safety.
- The package builds and installs as a normal Python 3.12 wheel, linting passes, and dependency checks report no broken requirements.

These tests prove current operability from one residential network. They do not guarantee that all videos, regions, cloud hosts, or future YouTube changes will behave identically.

## Architecture

```text
Business query or known URL
          |
          +--> Official YouTube search (API key required)
          |          |
          |          +--> video ID + title + channel + published time
          |
          +--> URL/ID normalization
                     |
                     +--> caption retrieval (no API key)
                                |
                                +--> normalized timestamped segments
                                           |
                                           +--> overlapping JSONL chunks
                                                      |
                                                      +--> analytics / LLM / RAG
```

Keeping discovery and retrieval separate is important. It lets a company replace either source without redesigning the downstream schema.

## Google account and Cloud project ownership

The original transcript project did not use a Google account. A Google account is needed only for the discovery functionality added in version 0.2.0.

For business use, do not create the API project under an employee's disposable personal account. Prefer:

- A company-managed Google Workspace identity.
- A dedicated Google Cloud project with a descriptive name such as `youtube-research-production`.
- At least two business administrators or an organization-level ownership process.
- Separate projects and keys for development, staging, and production.
- Documented ownership transfer and offboarding procedures.

Google states that a Google Account, a Cloud project, credentials, and enablement of YouTube Data API v3 are required. See the [YouTube Data API getting-started guide](https://developers.google.com/youtube/v3/getting-started).

## Create and secure the YouTube Data API key

1. Sign in to the [Google Cloud Console](https://console.cloud.google.com/) with the business-owned account.
2. Create or select a dedicated project.
3. Open **APIs & Services → Library**.
4. Enable **YouTube Data API v3**.
5. Open **APIs & Services → Credentials**.
6. Create a standard API key.
7. Add an API restriction limiting the key to **YouTube Data API v3**.
8. Add an application restriction appropriate to the deployment:
   - Server workload: restrict to known public IP addresses when operationally possible.
   - Browser workload: use HTTP-referrer restrictions, although this project is designed for server-side execution.
   - Mobile workload: use the relevant Android or iOS restriction.
9. Store the key in a secret manager or protected deployment environment variable.
10. Configure the application as `YOUTUBE_API_KEY`; never commit the real value.

This project sends the key in the `X-Goog-Api-Key` request header so it does not appear in the search URL. Google's current guidance recommends API restrictions and application restrictions and warns against embedding keys in source code. See [Manage API keys](https://docs.cloud.google.com/docs/authentication/api-keys) and [API key best practices](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices).

Local configuration:

```bash
cp .env.example .env
export YOUTUBE_API_KEY="replace-with-a-restricted-key"
```

The package reads the environment variable directly; it does not automatically load `.env`. A production process manager, CI/CD platform, container orchestrator, or secrets manager should inject it.

### API key versus OAuth

A standard API key associates public-data requests with a Google Cloud project for quota and administration. It does not sign in as a YouTube user and does not grant access to a person's private videos.

This project needs only a standard API key because it performs public search. OAuth 2.0 would be required for user-authorized operations such as accessing a signed-in user's private resources or modifying YouTube data. Those operations are deliberately outside this project's scope.

## Discovery API details

The implementation calls:

```text
GET https://www.googleapis.com/youtube/v3/search
```

It sends these parameters:

| Parameter | Purpose |
| --- | --- |
| `part=snippet` | Requests public title, description, channel, and publication metadata. |
| `type=video` | Excludes channel and playlist results. |
| `q` | Business search phrase. YouTube also supports `-` for exclusion and `|` for OR. |
| `maxResults` | One to 50 results in this project. |
| `order` | `relevance`, `date`, `rating`, `title`, or `viewCount`. |
| `channelId` | Optional restriction to one channel. |
| `publishedAfter` | Optional RFC 3339 lower publication bound. |
| `fields` | Reduces the response to fields used by the pipeline. |

Google's authoritative parameter definitions are in the [`search.list` documentation](https://developers.google.com/youtube/v3/docs/search/list).

Current limitations:

- The implementation fetches one search page, with a maximum of 50 results.
- It does not yet consume `nextPageToken` for pagination.
- Channel filtering performs a search within a channel; it is not exhaustive uploads-playlist enumeration.
- Search ordering and result relevance are controlled by YouTube and can change.
- Search metadata proves discoverability, not caption availability or fitness for a business purpose.

## Quota and capacity planning

As of August 8, 2026, Google's documentation describes a default project allocation of 100 `search.list` calls, 100 `videos.insert` calls, and 10,000 daily units shared by other endpoints. Google can change quotas, and the Cloud Console is the operational source of truth for a specific project.

This project only uses `search.list`; transcript retrieval does not use Google Data API quota. Each CLI search currently makes one `search.list` call and can request up to 50 results.

For higher-volume business use:

- Cache discovery results rather than repeating identical queries.
- Schedule searches at a controlled cadence.
- Deduplicate by canonical video ID before transcript retrieval.
- Monitor quota and errors in Google Cloud.
- Add pagination only when the business genuinely needs it.
- Complete Google's compliance audit before requesting additional quota.

See Google's [quota and compliance audit guidance](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits).

## Transcript retrieval details

Once a video ID is known, `fetch_transcript()` asks `youtube-transcript-api` for the preferred languages in order. The project currently defaults to English and records:

- Canonical video ID and watch URL.
- Selected caption language and language code.
- Whether captions are auto-generated.
- Segment text, start time, and duration.
- Chunk start/end times and segment count.

No YouTube Data API key is used for this stage. The upstream package uses an undocumented portion of YouTube's web-client interface and explicitly warns that it may break if YouTube changes that interface. See [`youtube-transcript-api` on PyPI](https://pypi.org/project/youtube-transcript-api/).

Expected retrieval failures include:

- Captions are disabled.
- No requested language is available.
- Video is private, removed, restricted, or unavailable in the deployment region.
- Automated access is blocked or rate-limited by YouTube.
- A cloud-provider IP is treated differently from a residential IP.
- YouTube changes its internal caption interface.

The application uses a 20-second default timeout and two retries with backoff for connection, read, `429`, and transient `5xx` failures. Batch processing reports failed videos, continues with the rest, writes successful records, and returns a nonzero status if any retrieval failed.

## JSONL contract

Each line is an independent `youtube_transcript_chunk` record. Core fields include:

```json
{
  "schema_version": 1,
  "record_type": "youtube_transcript_chunk",
  "chunk_id": "youtube:VIDEO_ID:0",
  "video_id": "VIDEO_ID",
  "source_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language_code": "en",
  "is_generated": true,
  "chunk_index": 0,
  "start_seconds": 0.0,
  "end_seconds": 90.0,
  "segment_count": 30,
  "text": "Transcript text..."
}
```

Records originating from discovery also include `title`, `channel_id`, `channel_title`, `published_at`, and `discovery_query`.

The schema is intentionally provider-neutral. A business can send it to an LLM, embed it, store it in object storage, load it into a warehouse, or index it in a search/vector system without changing ingestion.

## Business adaptation patterns

### Market and competitor research

- Search a defined set of topics or channels on a schedule.
- Preserve publication and channel metadata.
- Extract themes, claims, products, and named entities.
- Retain timestamps so analysts can verify every generated conclusion against the video.

### Internal learning library

- Use an approved source list rather than unrestricted discovery.
- Index chunks by topic and timestamp.
- Provide links back to the original video for context and attribution.
- Avoid representing auto-generated captions as authoritative quotations.

### Customer and industry intelligence

- Search product names, pain points, and relevant events.
- Deduplicate repeated or syndicated content.
- Apply a human review step before business decisions.
- Establish retention and deletion policies for stored text and derived data.

### RAG or knowledge assistant

- Treat transcript text as untrusted retrieved content, not instructions.
- Keep system instructions separate from transcript text.
- Require source links and timestamps in generated answers.
- Evaluate transcription errors, hallucinations, prompt injection, and stale content.
- Add access controls if the resulting corpus contains confidential annotations or user data.

## Production operating model

A production deployment should add:

1. A scheduler or job queue for discovery and retrieval.
2. A cache keyed by video ID, language, and retrieval date.
3. Structured error categories and retry/dead-letter handling.
4. Rate limits per worker and per outbound IP.
5. Metrics for searches, discoveries, transcript success, no-caption results, blocks, and latency.
6. Secret-manager injection for `YOUTUBE_API_KEY`.
7. Versioned storage for raw normalized segments and derived chunks.
8. Content and privacy review appropriate to the business.
9. Human verification for high-impact outputs.
10. A periodic live smoke test because transcript retrieval depends on an undocumented interface.

Do not solve cloud IP blocking by silently adding questionable proxy infrastructure. Evaluate providers, terms, jurisdiction, privacy, logging, and security explicitly.

## Policy, privacy, and content rights

Organizations using the official Data API must comply with the [YouTube API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service) and [Developer Policies](https://developers.google.com/youtube/terms/developer-policies). Google's current terms include privacy-policy and security obligations for API clients, and additional quota can require a compliance audit.

Separately, access to a transcript does not grant ownership of it. Before storing, redistributing, training on, or commercially exploiting transcript content, determine the applicable copyright, contract, privacy, and platform requirements. Generated captions can contain material errors, especially for names, numbers, medical terminology, legal statements, and specialized vocabulary.

## Recommended handoff checklist

- [ ] Business-owned Google Cloud project created.
- [ ] YouTube Data API v3 enabled.
- [ ] Standard API key restricted by API and application.
- [ ] Key stored outside source control.
- [ ] Search quota monitored.
- [ ] Content sources and business purpose documented.
- [ ] Privacy policy and retention rules reviewed.
- [ ] Transcript text treated as untrusted model input.
- [ ] Human-verification threshold defined.
- [ ] Error, block, and no-caption handling tested in the target hosting environment.
- [ ] Periodic live transcript smoke test scheduled.
- [ ] Terms and developer policies reviewed by the responsible business owner.

## Commands for a new organization

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install .
```

Known videos, no Google API key required:

```bash
yt-transcript VIDEO_ID_1 VIDEO_ID_2 \
  --languages en es \
  --output data/corpus.jsonl
```

Discover and retrieve public videos:

```bash
export YOUTUBE_API_KEY="restricted-business-key"

yt-transcript \
  --search "industry topic -irrelevant-term" \
  --search-limit 20 \
  --search-order date \
  --published-after 2026-01-01T00:00:00Z \
  --languages en \
  --output data/industry-corpus.jsonl
```

Start with a small, explicitly approved pilot corpus. Review results, failure rates, content rights, and operational costs before increasing volume.
