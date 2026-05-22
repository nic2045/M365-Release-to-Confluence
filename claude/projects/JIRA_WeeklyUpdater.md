# JIRA_WeeklyUpdater — Claude Instructions

@../CLAUDE.md

## FEATURES.md

After every finalized major change (feature, bug fix, behavior change) update `FEATURES.md` — add new buttons/options, adjust existing entries.

## Versioning

- `VERSION`-Datei enthält den vollen String `X.Y.Z (build YYMMDD.HHMM)` — wird via `__APP_VERSION__`-Placeholder in den UI-Branch-Badge injiziert
- Commit-Format: `release X.Y.Z (build YYMMDD.HHMM): <Kurzbeschreibung>`

## Jira Instance

Jira Data Center v10.3.19 (build 10030019, sha1: 95508b3).

- `createmeta` endpoint (`/rest/api/2/issue/createmeta`) returns 404 for the ITARCH project — use `/rest/api/2/field` for field discovery instead.
- Architekturservice custom field: `customfield_16706`
