# Changelog

## 0.2.0 - 2026-08-08

### Added

- Official YouTube Data API v3 video discovery by keyword.
- Search filters for channel, publication time, result order, and result count.
- Search metadata on transcript chunks: title, channel ID/name, publication time, and discovery query.
- Network timeouts and retry/backoff behavior for transcript requests.
- Atomic overwrite-mode JSONL output.
- Canonical video-ID deduplication across equivalent URL forms.
- Python 3.11–3.14 CI coverage.
- Business implementation guide covering Google Cloud ownership, API-key security, quota, policy, deployment, and verified test results.
- Deterministic discovery and CLI tests.

### Changed

- Raised the supported Python baseline to 3.11 and recommend Python 3.12.
- Replaced editable-install instructions with a standard wheel installation.
- Modernized Python packaging and license metadata.
- Send the Google API key through `X-Goog-Api-Key` rather than including it in the request URL.
- Clear stale overwrite-mode output when every requested transcript fails.

### Verified

- 27 deterministic tests pass.
- Formatting, linting, packaging, and dependency checks pass.
- Live retrieval succeeds for both manual and auto-generated English captions.
- Common watch, short, Shorts, embed, live, legacy `/v/`, nocookie, protocol-relative, and raw-ID inputs resolve correctly.
