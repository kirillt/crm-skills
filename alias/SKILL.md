---
name: alias
description: Resolve or register lightweight global aliases in `aliases.json`. Use when the user explicitly asks to look up, add, change, or remove an alias mapping between an arbitrary user-provided string and one canonical entity ID.
---

# Alias

## Overview

Use this skill to read or update the global alias registry in `aliases.json`.

`aliases.json` is a flat JSON object where:
- each key is an arbitrary user-provided string
- each value is one valid canonical entity ID

Values may point to companies or people.

## When To Use

Use this skill when the user explicitly asks to:
- look up an alias
- add or update an alias mapping
- remove an alias mapping
- verify what a string resolves to via `aliases.json`

Do not use this skill for general entity intake; use the `consider` skill family for that.

## Procedure

### Lookup

1. Read `aliases.json`.
2. Look up the provided string exactly as given.
3. If found, print the mapped canonical ID in chat.
4. If not found, report that the alias is unknown.

### Create or update

1. Try to resolve each provided argument as either:
   - an exact canonical ID, or
   - a persisted entity display name
2. Resolution target:
   - first try `companies/*.json`
   - if no company match exists, allow `people/*.json`
3. Stop and report to the user if:
   - both arguments resolve to persisted entities, or
   - neither argument resolves
4. If only one argument resolves:
   - treat the unresolved argument as the alias key
   - treat the resolved entity ID as the value
   - write/update the mapping in `aliases.json`
5. Report the stored mapping in chat.

### Remove

1. Read `aliases.json`.
2. Look up the provided alias key exactly.
3. If absent, report that there is nothing to remove.
4. If present, delete the mapping and report the removed key/value pair.

## Non-negotiable rules

- Keep `aliases.json` as a flat key-value mapping only.
- Do not guess between multiple possible entity matches; stop and ask instead.
- When an alias is used during resolution, any persisted structured reference must use the matching canonical `{id}`, never the alias spelling.

## Output

When you use this skill, execute the alias lookup/update/remove action directly instead of replying with an informal plan.
