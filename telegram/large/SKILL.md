---
name: telegram-large-chats
description: Sync and discover large Telegram chats using the durable Telegram scraper. Use when the user wants to scrape approved larger chats, review joined groups, and suggest additional large-chat scraping candidates.
---

# Telegram Large

## Overview

Use this skill for Telegram large-chat catchup and discovery.

This workflow is the large-chat counterpart to `$telegram-small-chats`, but it is cache/discovery-first rather than canonical-sync-first.

Use this skill when:
- the user explicitly asks to work through larger Telegram chats
- the user wants to run the approved large-chat scraper sequence
- the user wants joined-group discovery based on the durable Telegram scraper

This skill should run through `$batch`, not as one monolithic scrape/report step.

## Shared dependencies

Read these files first:
- `state/telegram/last-sync.json`
- `config/telegram/main.json`
- `config/telegram/large-chats.json`

Use this shared scraper:
- `.agents/skills/telegram/scripts/sync.py`

Use this auxiliary discovery helper:
- `.agents/skills/telegram/scripts/list.py`

Treat `large-chats-sync` in `state/telegram/last-sync.json` as the run's starting cutoff.

## Canonical scratch location

Start a fresh batch run for each invocation with:
- `$batch`
- `$task-register`

Create exactly one new timestamped scratch task for that run under:
- `scratch/telegram-large-chats/<YYYYMMDD-HHMMSS>.md`

Keep bulky artifacts for that run under:
- `scratch/data/telegram-large-chats/<YYYYMMDD-HHMMSS>/`

## Definition

In this repo, `small` means:
- direct messages
- groups with participant count strictly below `config/telegram/main.json` `small_group_max_participants`

So `large` means anything larger than that small-chat surface, especially:
- groups with participant count greater than or equal to that threshold
- broader channel/group scraping surfaces tracked in `config/telegram/large-chats.json`

## Goal

Run the durable Telegram scraper against the approved active targets since `large-chats-sync`, extract business insights from those refreshed message surfaces, then inspect large chats/channels and suggest additional relevant scraping candidates.

Primary outputs:
- refreshed Telegram raw cache under `cache/telegram/`
- batch-table business insights and discovery suggestions
- discovery suggestions for additional large-chat targets
- updated `large-chats-sync` state when a run completes successfully

## Procedure

1. Read `state/telegram/last-sync.json` and take `large-chats-sync` as the run cutoff.
2. Read `config/telegram/main.json`.
3. Read `config/telegram/large-chats.json`.
4. Start a fresh batch run using `$batch`, and initialize its scratch record with `$task-register`.
5. In that scratch record, store at minimum:
   - the cutoff date from `large-chats-sync`
   - the current batch size
   - the active-target list used for this run
   - the discovery source rule
   - processed insight items
   - pending insight items
   - the latest batch shown
   - the latest approval outcome
   - the next actionable step
6. Ensure the repo-local Python environment is available.
   - Prefer `.venv/bin/python`.
7. Gather source material for the run.
   - Run the scraper against the `active_targets` one by one, in listed order.
   - Use the configured channel ID for deterministic targeting.
   - Command pattern:
     - `.venv/bin/python .agents/skills/telegram/scripts/sync.py --since <large-chats-sync> <channel_id>`
   - Treat each target as an independent step.
   - If one target fails, report it clearly and continue with the remaining targets unless the failure blocks authentication or global scraper startup.
   - After the active-target sequence, run:
     - `.venv/bin/python .agents/skills/telegram/scripts/list.py large --since <large-chats-sync>`
8. Build the run's item set as insight items, not channel rows.
   - An item is one extracted business insight or one discovery suggestion.
   - If one channel produces three distinct business-relevant observations, that becomes three batch items.
   - Discovery suggestions for new large chats also become insight items in the same run.
   - Do not iterate the approval loop directly over raw channels unless a channel truly yields only one meaningful insight item.
9. Generate insight items from active scraped targets.
   - For each successfully scraped active target, do a lightweight first-pass review of the resulting message surface and extract:
     - whether new or recent messages contain business-relevant discussion
     - one concise insight per distinct business-relevant topic
     - an explicit proposed follow-up for each such insight
10. Generate discovery-suggestion items.
   - Review the joined chats returned by `list.py large`
   - discard ignored chats immediately; do not scrape them and do not cache their messages
   - for each new large chat candidate, record it into `config/telegram/large-chats.json` `under_consideration`
   - suggest one action for each candidate:
     - `promote`: move to `active_targets` for automatic scraping
     - `save for future`: keep in `under_consideration`
     - `ignore`: move to `ignore`
   - if the user does not confirm an action, default to `keep` by leaving the chat in `under_consideration`
   - compare against `active_targets`, `under_consideration`, and `ignore` from `config/telegram/large-chats.json` to avoid duplicates
   - prioritize names matching the configured discovery priorities
11. Phase A review batches:
   - process only up to the current batch size
   - show a mandatory batch table in chat for the next set of insight items
   - stop for approval or corrections
12. After each batch approval:
   - record the decision in the same batch scratch task
   - mark approved insight items as processed
   - leave corrected/rejected items with explicit disposition
   - if pending insight items remain, continue with the next batch in the same run
13. Apply approved consequences from the reviewed insight items.
   - For discovery items, move the channel to `active_targets`, keep it in `under_consideration`, or move it to `ignore` according to the approved action.
   - For active-target insight items, record the accepted interpretation and follow-up notes in the current run scratch task.
   - This workflow remains cache/discovery-first; active-target insight items do not by themselves imply canonical person/company persistence.
14. If the run completes cleanly enough to count as a refresh of the active-target sequence, update `state/telegram/last-sync.json`.
15. Mark the batch scratch task completed only when all approved insight items have been applied and the sync state has been advanced for the run.

## Non-negotiable rules

- This workflow is scraper/discovery oriented; it does not by itself imply canonical person/company persistence.
- Use `$batch` for the run container and `$task-register` to create the fresh run scratch task before the first batch.
- One invocation of this skill creates one fresh batch scratch task.
- Use `config/telegram/large-chats.json` as the source of channel preferences for active, under-consideration, and ignored targets.
- Use `config/telegram/main.json` as the source of truth for the small/large group threshold.
- Do not suggest ignored chats again.
- Do not scrape ignored chats; their messages must be discarded rather than cached.
- Do not scrape `under_consideration` targets by default unless the user explicitly asks.
- Keep the large-chat last-sync marker in `state/telegram/last-sync.json`, separate from `small-chats-sync`.
- Prefer the shared Telegram scraper in `.agents/skills/telegram/scripts/` rather than the old `tools/` location.
- Iterate the review loop over extracted business insights and discovery suggestions, not over raw channels.
- Do not advance `state/telegram/last-sync.json` until the current run's approved insight items are fully applied.

## Batch report

Use one mandatory batch table per reviewed batch of insight items:

`Source` | `Insight type` | `Business insight` | `Proposal` | `Default if unconfirmed`

Where:
- `Source` identifies the channel or discovery surface
- `Insight type` distinguishes active-target insight items from discovery suggestions
- `Business insight` is one concise extracted observation
- `Proposal` is the suggested follow-up or channel-disposition action
- `Default if unconfirmed` is usually `keep` for discovery items and blank when no default action applies

## Output

When you use this skill, start or continue the current fresh `$batch` run for Telegram large chats instead of answering with an informal plan.
