---
name: telegram-small-chats
description: Sync communication notes from small chats in Telegram. Use when the user wants to review, classify, scrape, and canonically sync Telegram small-chat history into people/company communication tracking.
---

# Telegram Small

## Overview

Use this skill to process Telegram small chats into canonical communication history.

This workflow owns the end-to-end small-chat sync loop:
- reviewing queued Telegram small chats in batches
- proposing `track`, `catch up`, or `discard` outcomes
- scraping full Telegram history for window-selected rows before proposing actions
- routing brand-new people/companies through the matching `consider` workflow
- finalizing approved canonical communication updates
- validating touched canonical/cache JSON

Use this skill when the user explicitly asks to work through Telegram small chats, or when a request is clearly about syncing small-chat communication backlog from Telegram.

Optional input:
- no input: process the full available window from `small-chats-sync` through today
- optional duration:
  - one integer `N`: process exactly `N` days forward from `small-chats-sync`
  - one `<number> <unit>` pair where unit is `day`, `days`, `week`, `weeks`, `month`, or `months`
  - examples:
    - if `small-chats-sync` is `2026-04-20`, then `$telegram-small 7` means the effective window is `2026-04-20` through `2026-04-27`
    - `$telegram-small 2 weeks` means `2026-04-20` through `2026-05-04`
    - `$telegram-small 1 month` means `2026-04-20` through `2026-05-20`
- optional batch-size override:
  - `batch <N>`
  - examples:
    - `$telegram-small batch 20`
    - `$telegram-small 1 day batch 20`

Read the Telegram family shared state first:
- `state/telegram/last-sync.json`
- `config/telegram/main.json`

Treat the `small-chats-sync` value there as the run's starting cutoff.
Derive one effective end date for the run:
- default: today's date in the repo timezone
- with bare integer input `N`: `small-chats-sync + N days`
- with `<number> <unit>` input:
  - `day(s)`: `small-chats-sync + N days`
  - `week(s)`: `small-chats-sync + 7 * N days`
  - `month(s)`: `small-chats-sync` shifted forward by `N` calendar months

Derive one effective batch size for the run:
- discovery default: `config/telegram/main.json` `discover-batch-size`
- persistence default: `config/telegram/main.json` `persist-batch-size`
- with input `batch <N>`: override both batch sizes for this invocation only

## Canonical scratch location

Start a fresh bundled run for each invocation with:
- `$bundle`
- `$task-register`

Create exactly one new parent scratch task for that run under:
- `scratch/telegram-small-chats/<YYYYMMDD-HHMMSS>.md`

Keep bulky artifacts for that run under:
- `scratch/data/telegram-small-chats/<YYYYMMDD-HHMMSS>/`

Use the shared Telegram helpers from:
- `.agents/skills/telegram/scripts/`

Do not resume or mutate the historical singleton file `scratch/telegram-small-chats.md` for new runs. Treat it as historical context only.

## Goal

Turn Telegram small-chat backlog inside the selected window into clean canonical communication history without skipping approval gates or bypassing entity-intake guardrails.

High-level phases:
1. Discovery phase: review small chats and classify them into `track`, `catch up`, or `discard`
2. Persistence phase: canonically process approved rows in batches
3. Finalization phase: complete any remaining final reconciliation or follow-up queue recorded in the live scratch task

Each invocation starts a fresh Discovery phase / Persistence phase / Finalization phase bundled run from the current `small-chats-sync` cutoff. Do not inherit completion state from older Telegram small-chats scratch runs.

## Decision rule

Use these action meanings:
- `track`: the approved outcome would create a new canonical person record
- `catch up`: the approved outcome only updates existing canonical person/company records
- `discard`: skip canonical processing for that row

Proposal heuristic:
- First decide whether the person or group is clearly business-related from identity, employer, tracked company context, prior known relationship, or visible same-domain alignment.
- Treat `about-us/intro.md` and the repo's `about-us/rubrics.py` as the positioning sources for what counts as Taran's working domain.
- Treat the contact as business-related when the visible context places them in Taran's working domain from those positioning sources, even if no defended employer is visible yet.
- Treat likely lead-generation, referral, partner-routing, or business-development sources as business-related even when the contact looks independent.
- If business relevance is clear, do not default to `remove` just because the visible Telegram exchange is thin.
- Do not label a contact as `remove` only because communication is one-way or unresponsive.
- Do not discard only because the thread is outbound-only or has no reply yet; attempted outreach is still useful to track so the same person is not contacted again by mistake.
- If the business surface is clear but the company is untracked, prefer company-consider staging over `remove`.
- If the business surface is clear but the employer is fuzzy, a lightweight independent person may still be valid.
- If only the dialog identity is visible and the full conversation has not been reviewed yet, do not discard solely because the employer is unclear.
- During the Discovery phase, if only the dialog identity is visible and the user states that the contact is a good partner, same-domain route, or likely lead/referral source, prefer `track` or `catch up` over `discard`.
- Thin and business-unclear contacts should usually stay `remove`.

## Procedure

1. Read `state/telegram/last-sync.json` first and take `small-chats-sync` as the run start date.
2. Read `config/telegram/main.json`.
3. Parse the skill input.
   - Start with the default discovery batch size from `config/telegram/main.json` `discover-batch-size`.
   - Start with the default persistence batch size from `config/telegram/main.json` `persist-batch-size`.
   - If the input is empty, set the effective end date to today and keep both default batch sizes.
   - Accept these input shapes:
     - one integer `N`
     - one `<number> <unit>` pair
     - `batch <N>`
     - one integer `N` followed by `batch <M>`
     - one `<number> <unit>` pair followed by `batch <M>`
   - If the input is one integer `N`, treat it as days and set the effective end date to `small-chats-sync + N days`.
   - If the input is one `<number> <unit>` pair, accept only `day(s)`, `week(s)`, or `month(s)`, then derive the effective end date using the duration rules above.
   - If the input contains `batch <N>`, override both batch sizes for this invocation with `N`.
   - Normalize singular and plural units the same way.
   - If the input does not match one of those accepted shapes, stop and ask for one of: no argument, one duration, `batch <N>`, or one duration plus `batch <N>`.
4. Start a fresh bundled run using `$bundle`, and initialize its parent scratch record with `$task-register`.
5. In that parent scratch record, store at minimum:
   - the start date from `small-chats-sync`
   - the effective end date for this invocation
   - the current discovery batch size
   - the current persistence batch size
   - whether each batch size came from config or an input override
   - the current phase
   - the source rule for the run
   - phase-level processed items
   - phase-level pending items
   - the latest batch shown
   - the latest approval outcome
   - the next actionable step
6. Discovery phase: small-chat review.
   - Run this phase through `$batch` inside the parent bundle scratch task.
   - Treat `small` as:
     - direct messages
     - groups with participant count strictly below `config/telegram/main.json` `small_group_max_participants`
   - Use `.agents/skills/telegram/scripts/list.py small --since <small-chats-sync> --until <effective-end-date>` as the stable collection source.
   - Build the Discovery phase item set from the dialogs returned there.
   - Before proposing an action for any Discovery phase row, ensure full conversation context is available:
     - run `.agents/skills/telegram/scripts/sync.py --since <small-chats-sync> --until <effective-end-date> --full-conversation --skip-cached <target>` for that row or batch
     - treat the date window as the selector for which chats enter the run, not as the limit on messages cached for a selected chat
     - if the target already has Telegram cache under `cache/telegram/by_id/<channel_id>/`, rely on that existing cache instead of re-scraping
     - then read the cached conversation context before generating the proposal
7. Discovery phase review batches:
   - process only up to the current discovery batch size
   - inspect prior canonical presence for each row
   - inspect the full cached Telegram conversation for each row, not only the dialog title or latest window message
   - generate proposals using the known action types `track`, `catch up`, and `discard`
   - show the mandatory batch table in chat:
     - `Channel | Action | Proposal | Company`
   - when company-consider candidates are present, print the attached real company-consider table immediately after the proposal
   - when people-consider candidates are present, print the attached real people-consider table immediately after the proposal
   - stop for approval or corrections
8. After each Discovery phase batch approval:
   - record the decision in the same parent bundle scratch task
   - mark approved items as processed for the Discovery phase
   - leave corrected/rejected items with explicit disposition
   - if more Discovery phase items remain, continue with the next Discovery phase batch inside the same parent scratch task
9. Persistence phase apply batches:
   - once the Discovery phase review set is complete, switch the bundle to the Persistence phase
   - run the Persistence phase through `$batch` inside the same parent bundle scratch task
   - process the approved `track` / `catch up` backlog in apply batches
   - use the full conversation cache prepared during the Discovery phase as the source for canonical communication updates
   - use `.agents/skills/telegram/scripts/sync.py --all <target>` only for explicit debug full-history re-syncs
   - process only up to the current persistence batch size
   - process the whole approved apply batch before moving on
   - route first-touch new-company candidates through `$consider-companies`
   - route first-touch new-person candidates through `$consider-people`
   - apply every approved reviewed-no-change / no-action outcome as a conscious no-op completion
   - update canonical communication history for touched tracked people/companies
   - run required cache follow-ups after canonical company changes
   - run all required validators and write logs under `logs/validators.log/`
   - record the applied outcomes back into the same parent bundle scratch task
10. Finalization phase:
   - once the Persistence phase apply set is complete, switch the bundle to the Finalization phase
   - finish any reconciliation required by the current run
   - verify that all approved work from this run is applied
   - only then update `state/telegram/last-sync.json` so `small-chats-sync` becomes the effective end date for this invocation
11. Mark the parent bundle scratch task completed only when all three phases of the fresh run are complete.

## Non-negotiable rules

- Do not create canonical people or companies directly from this skill; use `$consider-people`, `$consider-companies`, or `$consider` first when needed.
- Use `$bundle` for the run container and `$task-register` to create the fresh parent scratch task before the first phase.
- Discovery phase and Persistence phase should use `$batch` internally; Finalization phase stays as the final reconciliation phase.
- One invocation of this skill creates one fresh parent bundle scratch task; do not reuse the old singleton scratch file as the live run record.
- After the user approves a Persistence phase batch, apply the whole batch before moving on.
- Do not mark a Persistence phase batch completed until the current parent scratch task records the applied outcomes for the entire approved batch.
- A reviewed-no-change row is still part of batch finalization and must be consciously applied as a no-op completion.
- When a batch contains multiple new-company or new-person candidates, stage and apply all approved ones within that same batch unless the user explicitly defers some of them.
- Do not treat canonical entity files as proof that a fresh run or Persistence phase batch is complete unless the current parent scratch task records that completion.
- For communication syncing from one Telegram source, review earlier available Telegram communication from that same source first and backfill business-relevant prior history before finishing.
- Preserve business-relevant information canonically whenever the schema allows.
- Do not advance `state/telegram/last-sync.json` until the fresh run's Finalization phase is complete.
- Do not advance `state/telegram/last-sync.json` past the effective end date chosen for this invocation.

## Batch report

For proposal batches, use:

`Channel` | `Action` | `Proposal` | `Company`

Where:
- `Channel` identifies the Telegram handle or channel/group id plus the display name when useful
- `Action` is `track`, `catch up`, or `discard`
- `Proposal` explains the exact canonical action if approved
- `Company` names the related tracked or staged company surface when one exists

## Follow-on workflows

- New people: `$consider-people`
- New companies: `$consider-companies`
- Mixed first-touch intake: `$consider`
- Company cache refresh after canonical company edits: `$cache-companies`
- People cache follow-up after canonical person edits: `$cache-people`

## Output

When you use this skill, start or continue the current fresh `$bundle` run for Telegram small chats using the selected date window instead of answering with an informal plan.
