---
name: telegram-conversations
description: Batch-sync Telegram direct messages and below-threshold groups into canonical communication history using bounded Discovery, approved full-history Persistence, and consider-gated entity intake.
---

# Telegram Conversations

Use for Telegram direct messages and groups with participant count strictly below `config/telegram/main.json` `conversation_group_max_participants`.

## Inputs

Read first:
- `state/telegram/last-sync.json` -> `conversations-sync` is the run start date.
- `config/telegram/main.json` -> `batch-size`, `conversation_group_max_participants`, retry settings.

Accepted arguments:
- empty: process from `conversations-sync` through today in the repo timezone
- `N`: process `N` days from `conversations-sync`
- `N day(s)`, `N week(s)`, `N month(s)`: process that duration from `conversations-sync`
- `batch N`: override `batch-size` for this invocation
- duration plus `batch N`, for example `1 week batch 20`

Use one effective batch size for both Discovery and Persistence.

## Runtime

Use `.venv/bin/python` for Telegram helpers. If startup fails, verify Telethon with:
- `.venv/bin/python -c 'import telethon; print(telethon.__version__)'`

Do not use system `python3` unless the repo-local runtime is missing or broken.

## Scratch

Each invocation creates one fresh `$batch` run via `$task-register`:
- scratch: `scratch/telegram-conversations/<YYYYMMDD-HHMMSS>.md`
- bulky artifacts: `scratch/data/telegram-conversations/<YYYYMMDD-HHMMSS>/`

The scratch ledger, not cache or canonical files, proves run progress. Record per row:
- `chat_id`, `username`, `title`, `cache_path`
- Discovery batch number, approved action, and selected-window evidence dates
- bounded-context message ids
- Persistence status: `pending`, `applied`, `no-op`, `deferred`, or `discarded`
- linked canonical ids plus consider/cache follow-up outcomes

## Script Contracts

List candidates:
- `.venv/bin/python .agents/skills/telegram/scripts/list.py conversations --since <start> --until <end> --json`

Discovery bounded sync:
- `.venv/bin/python .agents/skills/telegram/scripts/sync.py --since <start> --until <end> --context-messages 100 <target>`

Use `username` as `<target>` when present, otherwise exact `chat_id`. During Discovery, read only the returned `context_message_ids` from `cache/telegram/by_id/<chat_id>/`; do not scan arbitrary older cache files.

Persistence full-history sync for approved `track` / `catch up` rows:
- `.venv/bin/python .agents/skills/telegram/scripts/sync.py --since <start> --until <end> --full-conversation <target>`

Use `--all` only for explicit debug/bootstrap full-history re-syncs.

## Decision Rules

Actions:
- `track`: create a new canonical person only through `$consider-people`
- `catch up`: update existing canonical person/company communication history
- `discard`: no canonical processing

Business relevance:
- Use `about-us/intro.md` as the concise positioning source.
- Use `about-us/leads-qualification.md` as the business-fit policy source for deciding whether a surfaced company/contact is in scope for our work.
- Do not approximate rubric/scoring policy locally in this skill; when a thread points to a possibly in-scope company surface, defer the actual relevance interpretation to the about-us policy or to the invoked consider workflow.
- Do not discard solely because a thread is thin, one-way, outbound-only, unanswered, or lacks a clear defended employer.
- If bounded context is insufficient but the row looks potentially in-scope under the about-us policy, propose deeper analysis instead of silently discarding.
- Thin and business-unclear rows can be discarded.

Evidence:
- Telegram display names, titles, and local labels are identity hints only; never use them as employer/role/affiliation evidence.
- Use message content, explicit counterparty statements, profile links, official sources, and existing canonical records for affiliation decisions.
- For new or unclear company surfaces, route evidence through `$consider-companies`; Telegram must not assign rubric IDs or score relevance.

## Consider Handoff

For likely first-touch `track` rows, run the matching consider workflow before showing the Telegram conversation-review table:
- `$consider-companies` for company/product/protocol/network surfaces
- `$consider-people` for person/contact surfaces
- `$consider` for mixed or unclear intake

Pass a compact evidence bundle: Telegram `chat_id`, `username`, `title`, proposed action, bounded-context message ids/snippets, and inferred person/company surface. Do not make `$consider-*` rediscover or rescan Telegram cache when that bundle is enough.

Show real consider review rows (`promote`, `hold`, `change`, `remove`), not placeholder “stage later” wording. Discovery approval with new entities means apply the matching consider outcomes during Persistence.

When a Discovery batch invokes any `$consider-*` skill, pass that skill's current required review table through `$display-table` as-is. Do not restate, hardcode, compress, or rename consider-skill columns here; the invoked consider skill owns its report schema. The Telegram conversation table may reference consider outcomes briefly after those outcomes are known.

## Batch Loop

Discovery Extract:
1. Take the next unprocessed `list.py conversations --json` rows up to the effective batch size.
2. Run bounded sync for each row.
3. Record exact handoff fields in the scratch ledger: conversation, message ids, person surfaces, company surfaces, existing canonical matches, and cache paths.
4. Inspect canonical presence and bounded context.
5. Do not show a conversation approval table from this stage unless extraction is blocked or ambiguous in a way that needs user input.

Company Consider:
1. Before people or conversation review, run `$consider-companies` for every unique new or unresolved company/product/protocol/network surface from the extracted batch.
2. Show only the invoked `$consider-companies` review output for this stage and stop for approval/corrections when there are company candidates.
3. If there are no company candidates, record the no-op in the scratch task and continue to People / Conversation Review.

People / Conversation Review:
1. With company outcomes known, run `$consider-people` or `$consider` where needed for person/contact surfaces.
2. Route invoked consider-skill review output through `$display-table` as-is when it has an approval gate.
3. Then route the mandatory Telegram conversation table through `$display-table` and stop for approval.

Mandatory Telegram conversation table:
`Channel` | `Action` | `Proposal` | `Company`

After approval:
- mark `discard` rows as `discarded`
- immediately process approved `track` / `catch up` rows from that Discovery batch
- split Persistence only if the approved actionable subset exceeds the effective batch size

Persistence:
- full-history sync the row before canonical updates so earlier Telegram communication can be backfilled
- never create new people/companies directly; use `$consider-people`, `$consider-companies`, or `$consider`
- update canonical communication history, run required cache follow-ups/validators, and record `applied` / `no-op` / `deferred`
- finish the current Discovery batch's Persistence subset before moving to the next Discovery batch

Finalization:
- reconcile from the ledger
- verify every row has a final disposition
- verify every first-touch handoff and touched company-cache follow-up is recorded
- only then set `state/telegram/last-sync.json` `conversations-sync` to the run end date
- never advance sync state past the effective end date

## Non-Negotiables

- One invocation creates one fresh batch scratch task.
- Run in rolling order: `Discovery Extract N -> Company Consider N -> People / Conversation Review N -> Persistence for N -> Discovery Extract N+1 -> Finalization`.
- Do not treat cache files or canonical files as proof that a fresh run phase is complete.
- Preserve business-relevant information canonically whenever the schema allows.
