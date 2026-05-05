---
name: cache-companies
description: Refresh company cache semantics for canonical companies. Use when approved or already-tracked companies need `cache/companies/*.json` created, validated, repaired, or fully regenerated, including after `$consider-companies` or when the user explicitly asks to refresh company cache metrics.
---

# Cache Companies

## Overview

Use this skill to regenerate semantic company cache JSONs from canonical company data.

This skill is the reusable cache-hydration/scoring surface for:
- approved companies coming out of `$consider-companies`
- manual refreshes of explicit company subsets
- repo-wide cache validation and repair
- full repo-wide cache regeneration

## Invocation

Use:
- `$cache-companies`
- `$cache-companies --regenerate`
- `$cache-companies <company names...>`

If company arguments are provided, treat the remainder as a semicolon-separated list.

Examples:
- `$cache-companies`
- `$cache-companies --regenerate`
- `$cache-companies Matter Labs; Cyberscope; Hypernative`

## Goal

Regenerate semantic cache JSONs under `cache/companies/*.json` from canonical `companies/*.json`.

Modes:
- default with empty input: check all companies for cache existence and valid schema; regenerate any missing or invalid cache entries
- `--regenerate`: erase all company cache JSONs and regenerate them from scratch for the full canonical company set
- explicit company list: regenerate only those companies, regardless of whether cache files already exist

## Inputs

- Canonical entities:
  - `companies/*.json`
  - `people/*.json`
- Derived entities:
  - `cache/companies/*.json`
- Positioning/scoring references:
  - `about-us/intro.md`
  - `about-us/leads-qualification.md`
  - `about-us/rubrics.py`
- Additional internal context:
  - `projects/`
- Optional external sources:
  - official website/docs
  - official GitHub org/repos
  - official LinkedIn/X/Twitter pages

## Non-negotiable rules

- This skill is cache-focused. It may fix canonical company data when research shows canon is incomplete or wrong, but its main output is cache.
- During regeneration, use reachable canonical company links (`website`, `linkedin`, `github`, `twitter`) for primary-source grounding.
- If research reveals canonical company facts, update `companies/*.json` first, then regenerate cache from that corrected canon.
- Do not infer semantic cache fields with Python heuristics.
- Do not default cache metrics. If you cannot calculate them from evidence plus best judgement with a stated basis, block the cache write.
- Record the canonical relevance terms in company `rubrics` / optional `transitive_rubrics` and ensure the deterministic score from `about-us/rubrics.py`, interpreted through `about-us/leads-qualification.md`, matches cache `relevance`.
- `chance_next` must be less than or equal to `chance_6m` unless explicitly justified.
- When concluding “no change” on cache-facing metrics, state which inputs were examined and why they do not move the score.
- Validate touched canonical company files with `../../consider/companies/scripts/validate-companies.py` when canon changed.
- Validate touched cache files with `scripts/validate-companies-cache.py`.
- In empty-input mode, treat Python cache validation as a repair signal: if a cache file is missing or fails validation, regenerate it.
- Batch size default: 50 companies.

## Resolution

When explicit company arguments are provided:
1. Resolve against `companies/*.json` by exact `"name"` match, case-insensitive.
2. If no direct match exists, check `aliases.json`.
3. If still unresolved, apply a typo-tolerant normalized match.
4. If multiple matches remain, stop for disambiguation.
5. If none exists, stop and tell the user the company must first go through `$consider-companies`.

## Procedure

1. Determine mode:
   - empty input: all canonical companies in check-and-repair mode
   - `--regenerate`: all canonical companies in full-regeneration mode
   - explicit company list: resolve the named company set and regenerate only those companies
2. If mode is `--regenerate`:
   - erase existing `cache/companies/*.json`
   - rebuild the full canonical company set from scratch
3. If mode is empty-input check-and-repair:
   - inspect the full canonical company set
   - detect cache files that are missing
   - validate existing cache files with `scripts/validate-companies-cache.py`
   - queue regeneration for any company whose cache file is missing or fails validation
4. If mode is explicit company list:
   - resolve the target company set
   - queue regeneration for every resolved target company regardless of existing cache presence
5. For each queued company in the batch:
   - read `about-us/leads-qualification.md`
   - read `about-us/rubrics.py`
   - read canonical `companies/<id>.json`
   - inspect the existing derived `cache/companies/<id>.json` when it already exists
   - read referenced `people/*.json` when needed
   - search the repo for the company `{id}` when extra context may affect cache interpretation, including former employees in people `past_career`
   - use reachable canonical company links for primary-source grounding
   - compute `relevance` from canonical `rubrics` and optional `transitive_rubrics`
   - decide and write:
     - `summary`
     - `importance`
     - `relevance`
     - `contacts`
     - `temperature`
     - `latest_comms`
     - `latest_comms_date`
     - `chance_next`
     - `chance_6m`
6. If research reveals missing or incorrect canonical company facts:
   - fix canon first
   - then derive cache from the corrected canon
7. Validate touched canonical company files when canon changed.
8. Validate touched cache files.
9. After each batch, stop and show a reviewable table.

## Batch report

Use a table with:

`Company` | `Mode` | `Relevance` | `Temperature` | `Latest comms` | `Notes`

## Definition of done

- Every queued target company has a valid cache JSON in the requested mode.
- Touched cache files validate.
- Any canonical company fixes required for trustworthy cache output have been applied or explicitly blocked.

## Output

When you use this skill, execute the cache batch and show the review table instead of answering with an informal plan.
