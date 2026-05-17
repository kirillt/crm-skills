---
name: consider
description: Route mixed or unclear new entity intake into the correct staged consideration workflow. Use when the user explicitly invokes `$consider`, or when the input mixes people and companies or the entity kind is unclear. Dispatch person/profile/relationship intake to `$consider-people` and organization/product intake to `$consider-companies`. Use this as the fallback guardrail before persisting any brand-new entity when the data kind is not yet clear.
---

# Consider

## Overview

Use this as the thin top-level manual dispatcher for new-entity intake when the input kind is mixed or unclear.

Keep detailed people rules in `$consider-people`.
Keep detailed company rules in `$consider-companies`.
Those downstream consider skills use `$batch` for the generic scratch-task batch loop.

## When To Use

Use this skill when:
- the user explicitly invokes `$consider`
- one message contains both people and companies
- the input may lead to canonical persistence but it is not yet clear whether the primary targets are people, companies, or both

If the intake is already clearly person-side, use `$consider-people` directly.
If the intake is already clearly company-side, use `$consider-companies` directly.

## Routing

1. Normalize the user input into explicit candidate items.
2. Collapse duplicate references that clearly point to the same real-world entity.
3. Split the items into a `people` bucket, a `companies` bucket, or both.
4. If the result is people-only, hand off to `$consider-people`.
5. If the result is companies-only, hand off to `$consider-companies`.
6. If the result is mixed:
   - run `$consider-people` for the people candidates
   - run `$consider-companies` for the explicit company candidates
   - avoid duplicate company creation if a person’s current employer is already present explicitly in the company bucket
7. Preserve the user’s original evidence sources so the downstream skill can use them.

## Guardrails

- Never create a brand-new `people/*.json` or `companies/*.json` directly from this skill.
- Never keep detailed people/company intake rules here when they belong in the sibling skills.
- If an authorized scratch task is already in progress and its rules explicitly allow persistence, follow that task instead of re-routing through this skill.
- Do not edit `aliases.json` unless the user explicitly asked for alias work.

## Output

When you use this skill, immediately hand off to `$consider-people` and/or `$consider-companies` instead of answering with an informal plan.
