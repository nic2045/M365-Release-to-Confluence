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
| `--limit N` | Cap the number of items processed. |
| `--title-prefix` | Prefix for generated page titles (default `[M365] `). |
| `--dry-run` | Process but do not write to Confluence. |
| `-v` | Debug logging. |

## Configuration

All configuration is via environment variables (see `.env.example`):

- **Graph:** `M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET`
- **AI:** `AI_PROVIDER`, `OUTPUT_LANGUAGE`, plus the keys for the chosen backend
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
