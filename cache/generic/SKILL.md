---
name: cache
description: Route cache-refresh requests into the correct cache workflow. Use when the user explicitly invokes `$cache`, or when the cache target kind is mixed or unclear. Dispatch current company-cache work to `$cache-companies`; reserve person-cache requests for `$cache-people`.
---

# Cache

## Overview

Use this as the thin top-level manual dispatcher for cache work when the target kind is mixed or unclear.

Keep detailed company-cache rules in `$cache-companies`.
Keep future people-cache rules in `$cache-people`.

## When To Use

Use this skill when:
- the user explicitly invokes `$cache`
- the request is clearly about cache refresh but the target kind is not yet clear
- one message may mix cache work for multiple entity kinds

If the request is already clearly about `cache/companies/*.json`, use `$cache-companies` directly.

## Routing

1. Normalize the requested cache targets.
2. Split the request into `companies`, `people`, or both.
3. If the result is companies-only, hand off to `$cache-companies`.
4. If the result is people-only, hand off to `$cache-people`.
5. If the result is mixed, dispatch each subset to its sibling cache skill.

## Guardrails

- Never mutate canonical entities or cache files directly from this router skill.
- Keep detailed cache-validation and cache-scoring rules in the sibling skills, not here.

## Output

When you use this skill, immediately hand off to `$cache-companies` and/or `$cache-people` instead of answering with an informal plan.
