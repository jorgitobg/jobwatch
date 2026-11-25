# jobwatch

A small command-line tool that reports **newly published remote roles** from public job-board APIs (Greenhouse, Ashby, Lever). It treats the parts that usually break a "scrape and notify" script as the actual work: a source that is down, state that gets corrupted, and job titles that are untrusted input.

**What it is today (v0.1):** standard-library only (no runtime dependencies), three provider adapters, a strict TOML config, durable state with atomic writes, and Markdown or JSON output. The offline demo uses synthetic data and needs no network.

**What it is not:** it does not scrape search engines or career pages, rank or score roles, apply for you, or send notifications (pipe the output to whatever you use). It reports what the providers list; it says nothing about quality or whether a role is still open.

## Quickstart

Python 3.11+.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
python -m jobwatch.demo              # offline, synthetic, deterministic
pytest                               # coverage gate: 90 percent

cp sources.example.toml sources.toml # then list the boards you follow
jobwatch --config sources.toml       # first run records a baseline
jobwatch --config sources.toml --json
```

State defaults to `~/.local/state/jobwatch/state.json` (`--state` to change it). Exit codes: `0` ok, `2` unusable config, `3` no source answered.

## Demo output

`python -m jobwatch.demo` (captured from a real run; all data is synthetic):

```text
## Run 1 (2026-11-01): first scan; one provider is down
Baseline recorded for: Example Co, Demo Works. Existing roles are not reported.

**Partial coverage**
- Sample Labs: http status 503
[sources answered: 2/3, remote roles listed: 2]

## Run 2 (2026-11-02): the provider is back; it is baselined now, not reported
Baseline recorded for: Sample Labs. Existing roles are not reported.
[sources answered: 3/3, remote roles listed: 3]

## Run 3 (2026-11-03): two new roles; hostile title and link are neutralised
**New remote roles (2)**
- **Example Co** — Data Engineer
  Remote · no valid link
- **Example Co** — Staff \*\*Backend\*\* Engineer \[apply here\]\(https://evil.example.test\)
  Remote \(EU\) · [Apply](https://boards.example.test/example-co/103)
[sources answered: 3/3, remote roles listed: 5]

## Run 4 (2026-11-04): nothing changed
(nothing to report)
[sources answered: 3/3, remote roles listed: 5]

## Run 5 (2026-11-05): state file is corrupt; kept aside, never silently reset
Baseline recorded for: Example Co, Sample Labs, Demo Works. Existing roles are not reported.

**Partial coverage**
- state file was unreadable; moved to state.json.corrupt and baseline re-recorded
[sources answered: 3/3, remote roles listed: 5]

corrupt copy kept: True
```

## Design

- **A source is baselined only after it answers once.** If a provider is down on the first run and up on the second, its existing roles are recorded silently instead of being reported as "new".
- **Failures are partial, not fatal.** Each source is fetched independently; errors are listed under "Partial coverage". If every source fails, state is not touched and the exit code is `3`.
- **State is never silently reset.** An unreadable or invalid state file is moved to `state.json.corrupt` and reported. Writes are atomic (temp file, fsync, rename), so a crash leaves the old file or the new one.
- **Retention is by recency.** The 5000 most recently seen ids are kept, not the lexically last ones.
- **Provider data is untrusted.** Titles and locations are stripped of control characters, length-capped and Markdown-escaped; only plain `https` links are rendered, otherwise "no valid link". Parsers tolerate wrong types and missing fields.
- **Bounded network use.** HTTPS only, a timeout, and a response cap of 5 MB by default (`--max-bytes N` raises or lowers it, 1 to 100,000,000 bytes). Retries are opt-in (`--max-attempts N`, default 1 = none, at most 10): only GET requests that fail with HTTP 429/500/502/503/504, a network error or a timeout are retried, with exponential backoff or a numeric `Retry-After` capped at 30 s, inside a 60 s total deadline. Permanent errors (other 4xx), oversized responses and non-HTTPS URLs are never retried, and a source that still fails leaves the saved state untouched. Config tokens must match `[A-Za-z0-9_-]{1,64}`, so a config cannot redirect a request to another host or path.

Decisions: [ADR 0001](docs/adr/0001-state-and-baselining.md), [ADR 0002](docs/adr/0002-untrusted-provider-data.md). Specification: [docs/spec/0001-jobwatch.md](docs/spec/0001-jobwatch.md).

## Checked against real providers

The tests use fake transports. As a one-off check on 2026-11-05 (not part of CI, since it depends on third parties), the real transport and parsers were run against public boards on all three providers and returned well-formed roles (one Greenhouse board returned 216 remote roles, one Ashby board 153, and two Lever boards 28 and 1). One very large Lever board (about 6 MB) was rejected by the 5 MB cap, which is the intended behaviour and also a limitation: pass a larger `--max-bytes` (for example `--max-bytes 10000000`) if you follow such a board. Memory use grows with the cap, and an oversized response is never retried.

## Limitations

- "Remote" is decided from provider fields (a location containing "remote" on Greenhouse, `isRemote` on Ashby, `workplaceType` on Lever). Providers differ, so expect false positives and misses.
- A role that disappears and reappears is not reported twice; it stays in state until it ages out of the retention window.
- One request per source per run, with no rate limiting; retries are opt-in (`--max-attempts`) and only for transient failures. Boards whose response exceeds the cap (5 MB by default) are skipped until you raise `--max-bytes`. Schedule it politely (for example daily).
- Only these three providers; adding one means a parser plus a URL template.

## Layout

- `src/jobwatch/config.py`: strict TOML config
- `src/jobwatch/sources.py`: URL templates and per-provider parsers
- `src/jobwatch/transport.py`: bounded HTTPS transport behind a `Transport` port
- `src/jobwatch/state.py`: versioned state, atomic writes, corrupt-file handling
- `src/jobwatch/radar.py`: scan, baselining and diff
- `src/jobwatch/render.py`: safe Markdown and JSON output
- `tests/`: no network

Apache-2.0. AI-assisted, human-reviewed.
