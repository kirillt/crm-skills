---
name: consider
description: Route new entity intake into the correct staged consideration workflow. Use when the input contains new companies, new people, LinkedIn/profile URLs, company URLs, screenshots, names, or mixed entity lists that may lead to canonical persistence. Choose `\companies\consider` for company-only input, `\people\consider` for person-only input, and split mixed input into the right buckets using best judgement. Handle one or more same-kind entities in a single request, but do not assume that multiple screenshots mean multiple entities. Use this skill as the default guardrail before persisting any brand-new entity outside an already-authorized scratch-task workflow.
---

# Consider

## Overview

Route freeform entity intake into the correct staged consideration task before canonical persistence.
Separate people from companies, handle mixed batches, and avoid direct entity creation when staged review is required.

## Decision Rule

Classify each incoming item into one of three buckets:
- `company`: route to `\companies\consider`
- `person`: route to `\people\consider`
- `mixed`: split into both buckets and run both consider flows as needed

Default signals for `person`:
- LinkedIn profile URLs such as `linkedin.com/in/...`
- Human-readable full names
- Profile screenshots centered on one individual
- Evidence about a person’s current role, employer, seniority, location, languages, or prior career

Default signals for `company`:
- Official company/homepage URLs
- LinkedIn company pages such as `linkedin.com/company/...`
- GitHub orgs, docs sites, product/company names used as organizations
- Evidence about staff, products, audits, relationships, or business relevance of an organization

Use best judgement for ambiguous text:
- If the item is primarily “who is this person?” treat it as `person`
- If the item is primarily “should we track this organization?” treat it as `company`
- If one message includes both people and companies, split it instead of forcing one route
- If multiple same-kind entities appear in one request, keep them as one batch for the corresponding consider task
- Do not infer “multiple screenshots = multiple entities”; first check whether the screenshots are multiple views of the same person or company
- Split screenshots into multiple entities only when there is clear evidence of distinct names, profiles, or organizations

## Routing

1. Normalize the user input into explicit candidate items.
2. Collapse duplicate references that clearly point to the same entity.
3. Put each item into a `people` bucket, a `companies` bucket, or both if the message clearly contains both entity types.
4. If the result is company-only, execute `\companies\consider <items...>`.
5. If the result is person-only, execute `\people\consider <items...>`.
6. If the result contains multiple people only, pass them together in one `\people\consider` invocation.
7. If the result contains multiple companies only, pass them together in one `\companies\consider` invocation.
8. If the result is mixed:
   - run `\people\consider` for the people candidates
   - run `\companies\consider` for explicit company candidates
   - avoid duplicate company creation if a person’s current employer is already present explicitly in the company bucket
9. Preserve the user’s original evidence sources so the target consider task can use them.

## Guardrails

- Never create a brand-new `companies/*.json` or `people/*.json` directly from this skill.
- Never bypass staged review when the entity is new.
- If an authorized scratch task is already in progress and its rules explicitly allow persistence, follow that task instead of re-routing through `$consider`.
- If a person’s employer is untracked, `\people\consider` already knows how to route that employer through `\companies\consider`; do not silently create the employer directly.
- If the same message contains screenshots or URLs that are enough to stage a person but not enough to justify a new employer canonically, keep the person staged and let the downstream consider task handle the blocker.
- When several screenshots are provided, treat them as additional evidence first, not as proof of multiple entities.

## Examples

- `One profile URL and three screenshots of the same person` -> `\people\consider ...`
- `Two profile URLs for two different people` -> one batched `\people\consider ...`
- `One company URL and one company LinkedIn page for the same organization` -> deduplicate, then `\companies\consider ...`
- `Two founders plus their startup website` -> split into people/company buckets and route both

## Output

When you use this skill, immediately route into the concrete consider task instead of answering with an informal plan.
