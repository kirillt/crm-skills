---
name: consider-people
description: Stage person-first intake through the people consideration workflow. Use when the input contains LinkedIn profile URLs, readable person screenshots, LinkedIn HTML/MHTML profile exports, human names, direct user-reported LinkedIn `Added` / `Accepted` events, or direct user-reported sent/received messages involving an untracked person that may lead to canonical persistence.
---

# Consider People

## Overview

Route person-first intake into the staged people consideration workflow before canonical persistence.

Use this skill for new or unresolved people, including relationship-state evidence that could otherwise tempt direct canonical creation.

## Trigger Conditions

Use this skill when the input could cause a brand-new person to be tracked canonically, including:
- a new LinkedIn profile URL
- a readable person screenshot
- a LinkedIn HTML/MHTML profile export
- a human-readable full name with enough context to treat it as a tracked person candidate
- a direct report that someone added us or accepted us on LinkedIn
- a direct report that the user sent or received a message involving an untracked person
- screenshots used as person/relationship evidence, not just identity evidence

The user does not need to invoke a task-template command for this skill to apply.

## Goal

Rapidly evaluate a user-provided set of people candidates without immediately polluting canonical person/company data.

High-level question:
- how useful is it to outreach to these people for Taran.Space business development?

This workflow:
1. stages new/targeted person-candidate records under `scratch/data/people/consider/`,
2. resolves every current employer against tracked company data,
3. runs `$consider-companies` for each untracked current employer before any canonical company/person promotion,
4. evaluates each person's outreach usefulness using the LinkedIn-style buyer/partner/action framework,
5. promotes approved people into canonical person tracking where appropriate,
6. runs `$cache-people` only after canonical person persistence in this workflow,
7. keeps touched tracked companies and people structurally consistent.

## Decision Rule

Treat these as person-side signals:
- LinkedIn profile URLs such as `linkedin.com/in/...`
- human-readable full names
- profile screenshots centered on one individual
- LinkedIn HTML/MHTML profile exports
- evidence about a person’s current role, employer, seniority, location, languages, or prior career
- LinkedIn connection-state evidence such as `Added` or `Accepted`
- outreach evidence such as “I sent him this” or “he replied”
- screenshots used as person/relationship evidence, not just identity evidence

Use best judgement for ambiguous text:
- if the item is primarily “who is this person?” treat it as person intake
- if multiple screenshots are provided, treat them as additional evidence first, not as proof of multiple people
- relationship-state updates for an untracked person still belong in this workflow even when the message is not phrased as an identity lookup

## Routing

1. Normalize the user input into explicit person candidates.
2. Collapse duplicate references that clearly point to the same person.
3. Preserve the user-provided evidence sources so the staged review can use them.
4. For a previously untracked person:
   - `Added` / `Accepted` evidence routes through this workflow
   - sent/received-message evidence routes through this workflow
   - screenshot-plus-URL evidence routes through this workflow
5. If a LinkedIn screenshot is provided without the profile URL, ask for the URL in the same reply and still treat the case as person consideration.
6. If a person's employer is not already tracked, pass that employer through `$consider-companies` rather than creating company canon directly.

## Procedure

1. Create the per-run scratch task and staging dir.
   - Record:
     - `Inputs (verbatim)`
     - `Staging dir`
     - `To process`
     - `Employer resolutions`
     - `Staging -> canonical mapping`
     - `Approved canonical actions`
     - `Persisted people (this run)`
2. Stage the explicit person candidates only.
3. Extract profile evidence for each staged person candidate.
   - Use the user-provided links/screenshots/exports first.
   - Do brief online research for the current employer and any materially relevant prior employers when the profile alone does not give enough business context.
   - Record only source-backed fields:
     - full name
     - public profile URL(s)
     - current role
     - current employer
     - current-role start month/year when shown
     - materially relevant prior employers / prior roles
     - location and alternative communication languages when defensible
   - If a profile is too cropped to identify the role/company reliably, ask for an additional screenshot showing the top card plus the current-role block.
   - If the full name is not visible, do not substitute a title like `COO` into the canonical target; ask for a clearer screenshot instead.
   - Keep screenshots and OCR-like extracts in scratch only, never in canonical entities.
4. Resolve the current employer for each staged person candidate.
   - If the employer is already tracked:
     - use the canonical `companies/*.json` entity plus `cache/companies/*.json` to inform the person review
     - if the company cache is missing/stale/invalid, block on refreshing it before final person promotion
   - If the employer is not tracked:
     - if the employer looks relevant enough to become a tracked company, call `$consider-companies` once per unique untracked employer
     - do not create canonical company or cache files directly from this workflow
     - wait for the company-consider approval outcome before promoting people tied to that employer
   - For materially relevant prior employers:
     - use brief research to improve the person's usefulness review
     - do not silently create canonical company tracking from prior-employer context alone
   - If the employer remains unresolved or unapproved:
     - keep the person staged
     - do not silently create canonical company tracking
     - only persist the person independently if the user explicitly approves doing so without a tracked employer link
5. Evaluate outreach usefulness for each staged person candidate.
   - Classify the track:
     - `buyer` if the person works at a protocol/app/exchange/infra team that plausibly buys security work
     - `partner` if the person works at a security firm, dev shop, recruiter/talent agency, advisory, or similar service provider that could refer/subcontract work
     - `unknown` otherwise
   - If at least one profile is `partner` and the run has not explicitly specified how to handle partners, stop and ask one clarifying question:
     - `For this run, should potential partners be treated as "write immediately" or "save for future"?`
   - Choose the recommended action:
     - `write immediately`
     - `send connection request and save for future case`
     - `skip, don't spend time`
   - Estimate:
     - `chance (next week)`
     - `chance (6 months)`
   - Use observable signals only:
     - the person’s current role/seniority
     - the employer’s tracked cache metrics (`summary`, `importance`, `relevance`, `temperature`, `chance_next`, `chance_6m`)
     - prior employers when they materially change business usefulness
     - existing repo communication/context if the person is already tracked
   - Keep an internal person-relevance judgement for persistence decisions:
     - if the person is not useful to outreach directly but works at a relevant company, use `1%` as the floor
     - if the person is truly `0%`, do **not** persist the profile canonically
6. Show the staged review batch and stop for approval.
   - Always render the staged review in chat as a markdown table that includes the current suggestion for every candidate in the batch, even for single-item batches or when surrounding narrative context is also provided.
   - The table must include a `Blockers` column. Use `none` only when there is no unresolved blocker.
   - If `$consider-companies` was invoked as a sub-step for any employer in the batch, the people review table must reflect that dependency explicitly instead of pretending the employer is fully approved already.
7. Commit the approved batch immediately.
   - `promote`:
     - create/update the canonical person state as approved
     - if a canonical person entity was created or updated, add that person to `Persisted people (this run)`
   - `change`:
     - update the existing canonical person state as approved
     - if a canonical person entity was updated, add that person to `Persisted people (this run)`
   - `remove`:
     - if the item exists only in staging, drop the staged item only
     - if the action removes existing canonical person tracking, require explicit approval and then apply exactly that approved action
8. If `Persisted people (this run)` is non-empty, run `$cache-people` on that set.
   - Because people-cache is currently a stub/no-op surface, this handoff must not block successful person persistence.
   - If this run did not actually persist any canonical person entities, skip the cache step.
9. Validate all touched canonical JSON before finishing.
   - `people/*.json` -> `scripts/validate-people.py`
   - `companies/*.json` when company linkage changed -> `../companies/scripts/validate-companies.py`
   - `cache/companies/*.json` when touched through the company sub-step -> `../../cache/companies/scripts/validate-companies-cache.py`
10. Mark the scratch task completed after the final approval gate (or immediately in explicit no-pause mode if there is no blocker).

## Non-negotiable rules

- This workflow must produce a reviewable batch report before canonical changes.
- The staged review report shown in chat must always include a table with the current suggestion for every candidate in the batch.
- Every considered person must be grounded in explicit profile evidence; do not guess missing current employer/role details.
- Do brief online research for the current employer and any materially relevant prior employers when needed to evaluate the candidate cleanly.
- Every untracked current employer must go through `$consider-companies` before canonical company/person promotion.
- Use tracked company cache data whenever the employer already exists canonically.
- Do not silently create canonical company tracking from a people-only workflow, whether the signal comes from the current employer or a prior employer.
- All unresolved blockers must be shown in the staged review table's `Blockers` column. Do not present a blocked candidate as unqualified `promote`.
- `Relevance: 0%` means the profile must not be persisted canonically.
- `Relevance: 1%` is the floor for “person not directly useful, but current employer is relevant.”
- New canonical company creation is never allowed directly from this workflow; employer promotion must happen through approved `$consider-companies`.
- Use `$cache-people` only when this workflow actually persisted canonical person entities.
- Never create a brand-new `people/*.json` directly from first-touch intake outside this staged workflow.
- Never bypass staged review because the evidence feels “good enough”.
- Do not edit `aliases.json` unless the user explicitly asked for alias work.
- A direct profile/contact surface is required before clean canonical person registration; evidence-only cases still belong in staged consideration first.

## Batch report

Use a table with:

`Person` | `Current role` | `Company` | `Company status` | `Track` | `Recommended action` | `Chance (next week)` | `Chance (6 months)` | `Suggestion` | `Blockers` | `Why`

Where:
- `Person` is the staged candidate's full name
- `Current role` is the current role title
- `Company` is the resolved current employer
- `Company status` is one of `tracked`, `under consideration`, `untracked`, `blocked`
- `Track` is one of `buyer`, `partner`, `unknown`
- `Recommended action` is one of `write immediately`, `send connection request and save for future case`, or `skip, don't spend time`
- `Blockers` lists unresolved issues that block or condition canonical changes; use `none` only when no blocker remains
- `Why` is a short 1-line rationale for the current suggestion

Suggestion values should be one of:
- `promote`
- `change`
- `hold`
- `remove`

## Examples

- `One profile URL and three screenshots of the same person` -> one staged people-consider run
- `Two profile URLs for two different people` -> one batched staged people-consider run
- `He added me yesterday https://www.linkedin.com/in/...` -> staged people-consider
- `I sent him this:` plus profile URL or screenshot -> staged people-consider
- `A LinkedIn mobile screenshot plus an MHTML export of the same profile` -> one staged people-consider run
- `One profile URL and multiple screenshots of the same person` -> one staged people-consider run

## Output

When you use this skill, execute the staged people-consider workflow and show the required approval table instead of answering with an informal plan.
