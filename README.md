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

```bash
# Process changes from the last 30 days, both sources, without writing (preview):
m365-to-confluence --since-days 30 --dry-run -v

# Publish the 10 most recent roadmap items to Confluence:
m365-to-confluence --source roadmap --limit 10
```

| Flag | Description |
| --- | --- |
| `--source {both,message-center,roadmap}` | Which source(s) to read (default `both`). |
| `--since-days N` | Only items modified within the last N days. |
| `--limit N` | Cap the number of items processed (e.g. `--limit 3` while developing). |
| `--quarter "Q3 2026"` | Only items detected for that target quarter. |
| `--force` | Reprocess everything, ignoring the unchanged-item cache. |
| `--state-file PATH` | Local state file for skip/slip tracking (default `m365_state.json`). |
| `--title-prefix` | Prefix for generated page titles (default `[M365] `). |
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
- A **per-quarter dashboard page** is created/updated listing all features of that quarter.

## Saving tokens

- Unchanged items are skipped automatically (state file); only new/changed items hit the LLM.
- The system prompt is sent with **prompt caching** (Anthropic) so the standards block is cheap to reuse.
- Use `--since-days`, `--limit`, a cheaper model (`ANTHROPIC_MODEL=claude-haiku-4-5`) or `AI_PROVIDER=local`.

## Configuration

All configuration is via environment variables (see `.env.example`):

- **Graph:** `M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET`
- **AI:** `AI_PROVIDER`, `OUTPUT_LANGUAGE`, the keys for the chosen backend, and optional
  `ORG_CONTEXT` / `ORG_CONTEXT_FILE` to tailor recommendations to your environment
- **Confluence:** `CONFLUENCE_BASE_URL`, `CONFLUENCE_TOKEN` (PAT — `ConfluencePAT` also accepted), `CONFLUENCE_SPACE`, `CONFLUENCE_PARENT_PAGE_ID`

## Development

```bash
ruff check .
ruff format --check .
python -m pytest
```

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
