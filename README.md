# M365 Release to Confluence

> Read current changes and upcoming rollouts from the Microsoft 365 platform,
> summarise them with an LLM, and publish them to Confluence following your standards.

The tool pulls from **two sources**, merges and de-duplicates them, runs each
item through a **pluggable LLM**, and writes a consistent change note to
**Confluence Server / Data Center** (one page per item, idempotent on rerun).

```
Message Center (Graph) ─┐
                        ├─► aggregate ─► LLM (Anthropic | Azure OpenAI | local) ─► Confluence
M365 roadmap (public) ──┘
```

## Sources

| Source | What it provides | Auth |
| --- | --- | --- |
| **Message Center** (`/admin/serviceAnnouncement/messages`) | Tenant-specific changes & rollouts | Entra ID app with `ServiceMessage.Read.All` |
| **M365 roadmap** (`releasecommunications/api`) | Public upcoming rollouts | none |

## AI backends (pluggable)

Set `AI_PROVIDER` to one of:

- `anthropic` — Claude via the Anthropic SDK (prompt caching enabled).
- `azure_openai` — an Azure OpenAI deployment.
- `local` — any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, ...).

The house style for every change note lives in one place —
`STANDARDS` in [`src/m365_confluence/ai/prompts.py`](src/m365_confluence/ai/prompts.py).
Edit it to match your wording, structure and required fields.

## Setup

```bash
pip install -e ".[dev]"     # or ".[all]" for runtime only
cp .env.example .env        # then fill in the values (.env is gitignored)
```

## Usage

> **Safe by default: nothing is written to Confluence without human approval.**
> A normal run only produces editable drafts (`review.json`). Publishing happens via the
> review UI ("Publish"), `--from-review`, or an explicit `--approve` on the command line.

```bash
# Preview only, never writes:
m365-to-confluence --since-days 30 --dry-run -v

# Default run -> writes drafts to review.json, publishes NOTHING:
m365-to-confluence --source roadmap --limit 10

# Explicitly approve publishing to Confluence (e.g. an ad-hoc human run):
m365-to-confluence --source roadmap --limit 10 --approve
```

| Flag | Description |
| --- | --- |
| `--source {both,message-center,roadmap}` | Which source(s) to read (default `both`). |
| `--since-days N` | Only items modified within the last N days. |
| `--limit N` | Cap the number of items processed (e.g. `--limit 3` while developing). |
| `--quarter "Q3 2026"` | Only items detected for that target quarter. |
| `--major-only` | Only Message Center items flagged as a major change. |
| `--action-required` | Only items with an action-required deadline. |
| `--product NAME` | Only items touching this product (repeatable, substring, e.g. `--product Teams`). |
| `--list-products` | List products found in the source(s) with counts, then exit (no LLM/Confluence). |
| `--pick-products` | Interactively multi-select products before running (numbers, ranges, or `all`). |
| `--category NAME` | Only items in this MC category (repeatable, e.g. `planForChange`). |
| `--force` | Reprocess everything, ignoring the unchanged-item cache. |
| `--item-pages {none,major,all}` | Individual page per feature: none, only major changes (default), or all. Dashboards are always created. |
| `--state-file PATH` | Local state file for skip/slip tracking (default `m365_state.json`). |
| `--changelog-file PATH` | Local changelog file driving the Changelog page (default `m365_changelog.json`). |
| `--title-prefix` | Prefix for generated page titles (default `[M365] `). |
| `--review-out PATH` | Process items and write editable drafts to PATH; publish nothing. |
| `--from-review PATH` | Publish edited drafts from PATH to Confluence without calling the LLM. |
| `--approve` | Explicit human approval to write to Confluence. Without it a run only writes drafts. |
| `--dry-run` | Process but do not write to Confluence (and do not save state). |
| `-v` | Debug logging for this tool. |
| `--debug-http` | Also show raw HTTP logs from httpx/anthropic/openai. |

## Quarters, slip detection & dashboards

- Each note gets a **target quarter** (LLM-derived, with a regex/date hint) and an
  **evergreen decision** (`Activate` / `Deactivate` / `Communicate` / `Monitor`) with a rationale.
- A local **state file** records a content hash per item, so **unchanged items are skipped**
  on later runs (saves tokens). Use `--force` to override.
- When an item's target quarter moves later than last seen, it is flagged as a **slip**
  (warning banner on the page; marked on the dashboard).
- A **per-quarter dashboard page** is created/updated listing all features of that quarter
  (with a short description column, so it stands on its own without per-feature pages).
- By default an **individual page is only created for major changes** (`--item-pages major`);
  use `none` for dashboards-only or `all` for a page per feature.
- The decision shows as a **coloured status badge** (Activate=green, Communicate=blue, Monitor=yellow, Deactivate=red); slips get a red badge.
- A **Changelog page** records each run's new/changed/slipped counts.

## Saving tokens

- Unchanged items are skipped automatically (state file); only new/changed items hit the LLM.
- The system prompt is sent with **prompt caching** (Anthropic) so the standards block is cheap to reuse.
- Use `--since-days`, `--limit`, a cheaper model (`ANTHROPIC_MODEL=claude-haiku-4-5`) or `AI_PROVIDER=local`.

## Review & edit before publishing

A human-in-the-loop workflow: generate drafts, edit them (CLI or web UI), then publish
without re-running the LLM.

```bash
# 1. Generate editable drafts (no Confluence write, no creds needed)
m365-to-confluence --source roadmap --review-out review.json

# 2a. Edit review.json by hand, OR
# 2b. Launch the web UI to review/edit (needs the 'ui' extra)
m365-to-confluence-ui --review-file review.json   # http://127.0.0.1:8765

# 3. Publish the edited drafts (no LLM call)
m365-to-confluence --from-review review.json
```

The UI lets you edit title, target quarter, decision, CAB flag/recommendation, summary,
impact and recommended action per item, then **Save** and **Publish** (with a dry-run toggle).

## Configuration

All configuration is via environment variables (see `.env.example`):

- **Graph:** `M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET`
- **AI:** `AI_PROVIDER`, `OUTPUT_LANGUAGE`, the keys for the chosen backend, and optional
  `ORG_CONTEXT` / `ORG_CONTEXT_FILE` to tailor recommendations to your environment
- **Confluence:** `CONFLUENCE_BASE_URL`, `CONFLUENCE_TOKEN` (PAT — `ConfluencePAT` also accepted), `CONFLUENCE_SPACE`, `CONFLUENCE_PARENT_PAGE_ID`

## Development

```bash
make dev        # editable install with all extras
make check      # lint + format check + tests (what CI runs)
make dry-run    # preview a run without writing to Confluence
make help       # list all targets
```

Equivalent without make:

```bash
ruff check .
ruff format --check .
python -m pytest
```

## Production / Container

One image runs either the **batch job** (scheduled) or the **review UI** (optional service).
Configuration comes from environment variables; state/changelog/review files persist on a
mounted volume (`/data`). Never bake secrets into the image.

The recommended prod flow keeps a human in the loop: the **scheduled job refreshes drafts**
(never writes to Confluence), and a person **approves via the UI** (or `--from-review`).

```bash
docker build -t m365-release-to-confluence .

# Scheduled job: refresh drafts only (no --approve -> writes /data/review.json, publishes nothing)
docker run --rm --env-file .env -v "$PWD/data:/data" m365-release-to-confluence \
  m365-to-confluence --source both --since-days 2 --review-out /data/review.json \
  --state-file /data/m365_state.json --changelog-file /data/m365_changelog.json

# Review UI (human approval): edit, then click Publish
docker run --rm -p 8765:8765 --env-file .env -v "$PWD/data:/data" m365-release-to-confluence \
  m365-to-confluence-ui --host 0.0.0.0 --review-file /data/review.json
```

Or with compose: `docker compose up -d ui` (UI) and `docker compose run --rm job` (draft refresh).

### Scheduling

**Cron** (daily 06:00, draft refresh only — approval stays with a human in the UI):

```cron
0 6 * * * docker run --rm --env-file /opt/m365/.env -v /opt/m365/data:/data \
  m365-release-to-confluence m365-to-confluence --source both --since-days 2 \
  --review-out /data/review.json \
  --state-file /data/m365_state.json --changelog-file /data/m365_changelog.json
```

**Kubernetes CronJob** (sketch): a `CronJob` running the same image/command daily (draft
refresh), env from a `Secret`, `/data` on a `PersistentVolumeClaim`; the UI runs as a
`Deployment`+`Service` for human review and approval.

## Layout

```
src/m365_confluence/
├── cli.py            # entry point (m365-to-confluence)
├── config.py         # env-based configuration
├── models.py         # ChangeItem, ProcessedItem
├── pipeline.py       # fetch -> aggregate -> process -> publish
├── sources/          # message_center, roadmap, aggregate
├── ai/               # providers, factory, prompts (STANDARDS), processor
└── confluence/       # Server/DC REST client (PAT)
```
