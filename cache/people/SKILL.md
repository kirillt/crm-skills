---
name: cache-people
description: Reserved entrypoint for future people-cache workflows. Use when the user explicitly asks for people-cache refresh, validation, repair, or regeneration, or as the post-persistence handoff from `$consider-people` after canonical people entities were updated. Today this skill is a non-blocking no-op because there is no active `cache/people/*.json` model yet.
---

# Cache People

## Overview

This skill is currently a no-op stub for future people-cache workflows.

There is no active canonical `cache/people/*.json` model yet.

## Invocation

Use:
- `$cache-people`
- `$cache-people --regenerate`
- `$cache-people <person names...>`

If person arguments are provided, treat the remainder as a semicolon-separated list.

Examples:
- `$cache-people`
- `$cache-people --regenerate`
- `$cache-people Alice; Bob`

## When To Use

Use this skill only when:
- the user explicitly asks for a people-cache workflow
- `$consider-people` calls it after persisting canonical person entities
- cache work is clearly person-side and cannot be satisfied by current canonical people data

## Goal

Accept the same user-facing cache API shape as `$cache-companies` while keeping people-cache requests non-blocking until a real `cache/people/*.json` model exists.

Modes:
- default with empty input: acknowledge that there is no active people-cache model, so there is nothing to validate or repair
- `--regenerate`: acknowledge that there is no active people-cache model, so there is nothing to erase or rebuild
- explicit person list: acknowledge the requested targets, but explain that there is no active people-cache model to regenerate for them

## Current Behavior

1. Determine mode:
   - empty input
   - `--regenerate`
   - explicit person list
2. Confirm that there is no active canonical `cache/people/*.json` model yet.
3. If this skill was invoked as a post-persistence handoff from `$consider-people`, treat the call as a successful no-op and do not block completion.
4. If the real need is person tracking or enrichment, redirect to `$consider-people` instead.
5. If the real need is company-cache refresh derived from person/company changes, redirect to `$cache-companies`.
6. If the request was explicit `--regenerate` or an explicit person list, state that the API shape is accepted but currently has no cache-side effect because people-cache is not implemented.

## Output

When you use this skill today, either complete as a no-op post-persistence hook or explain that people-cache is not implemented yet and redirect to the closest supported skill.
