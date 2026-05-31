---
name: telegram-large-groups
description: Batch-sync approved large Telegram groups/channels, extract business insights, and discover additional large-group targets without direct canonical persistence.
---

# Telegram Large Groups

Use for Telegram groups/channels outside the conversation surface. A `conversation` is a direct message or a group with participant count strictly below `config/telegram/main.json` `conversation_group_max_participants`; large groups are everything larger plus broadcast channels.

## Inputs

Read first:
- `state/telegram/last-sync.json` -> `large-groups-sync` is the run cutoff.
- `config/telegram/main.json` -> shared `batch-size`, threshold, retry settings.
- `config/telegram/large-groups.json` -> `active_targets`, `under_consideration`, `ignore`, `discovery_priorities`.

If `large-groups-sync` is `null`, stop and ask the user for a bootstrap cutoff date before scraping active targets. Do not use `--all` unless the user explicitly requests debug/bootstrap full-history scraping.

Use `.venv/bin/python` for Telegram helpers.

## Scratch

Each invocation creates one fresh `$batch` run via `$task-register`:
- scratch: `scratch/telegram-large-groups/<YYYYMMDD-HHMMSS>.md`
- bulky artifacts: `scratch/data/telegram-large-groups/<YYYYMMDD-HHMMSS>/`

Record cutoff, batch size, active targets, discovery source, processed/pending insight items, latest approval, and next action.

## Script Contracts

Sync each approved active target by ID:
- `.venv/bin/python .agents/skills/telegram/scripts/sync.py --since <large-groups-sync> <channel_id>`

Discover large groups/channels as structured rows:
- `.venv/bin/python .agents/skills/telegram/scripts/list.py large-groups --since <large-groups-sync> --json`

Use the shared scripts under `.agents/skills/telegram/scripts/`; do not use old `tools/` locations.

## Item Model

Batch items are insights, not raw channels:
- one distinct business-relevant observation from an active target
- one proposed follow-up for an active-target observation
- one discovery suggestion for a new large group/channel

If one channel yields three distinct observations, create three batch items.

Use the about-us policy stack for the business-relevance boundary:
- `about-us/intro.md` for concise positioning context
- `about-us/leads-qualification.md` for detailed business-fit policy

Do not assign rubric IDs or score company relevance directly inside this skill; when an insight suggests first-touch company/person tracking, defer that interpretation to the matching `$consider-*` workflow.

## Discovery Rules

For active targets:
- scrape targets listed in `active_targets`, one by one, using configured IDs
- continue after per-target failures unless authentication/session startup is globally blocked
- extract concise business insights and proposed follow-ups from newly scraped messages

For joined-group discovery:
- review `list.py large-groups --json` rows
- compare against `active_targets`, `under_consideration`, and `ignore`
- never scrape ignored groups; discard ignored-group messages rather than caching them
- never scrape `under_consideration` targets unless explicitly asked
- for each new candidate, record it under `under_consideration` and propose:
  - `promote`: move to `active_targets`
  - `save for future`: keep under consideration
  - `ignore`: move to `ignore`
- if the user does not confirm an action, default to `keep`

## Consider Boundary

This workflow is cache/discovery-first. Large-group insights do not by themselves imply canonical person/company persistence.

If the user approves canonical person/company persistence from an insight, route first-touch intake through `$consider-people`, `$consider-companies`, or `$consider` with a compact evidence bundle. Never write canonical people or companies directly from this skill.

## Batch Loop

1. Start the fresh `$batch` scratch task.
2. Sync active targets and discover candidate groups/channels.
3. Build the next insight-item batch up to `config/telegram/main.json` `batch-size`.
4. Route the mandatory table through `$display-table` and stop for approval.
5. Apply approved consequences and record them in scratch.
6. Continue until all insight items are processed.
7. Advance `state/telegram/last-sync.json` `large-groups-sync` only after the run is fully applied.

Mandatory table:
`Source` | `Insight type` | `Business insight` | `Proposal` | `Default if unconfirmed`

## Non-Negotiables

- One invocation creates one fresh batch scratch task.
- Use `config/telegram/large-groups.json` as the source of active, under-consideration, and ignored targets.
- Do not suggest ignored groups again.
- Iterate review over business insights/discovery suggestions, not raw channels.
- Do not advance `large-groups-sync` before approved insight items are fully applied.
