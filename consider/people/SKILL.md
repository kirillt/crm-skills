---
name: consider-people
description: Stage person-first intake through the people consideration workflow. Use when the input contains LinkedIn profile URLs, readable person screenshots, LinkedIn HTML/MHTML profile exports, human names, direct user-reported LinkedIn `Added` / `Accepted` events, or direct user-reported sent/received messages involving an untracked person that may lead to canonical persistence. This skill owns people-side review and persistence logic while using `$batch` for the generic scratch-task batch loop.
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
- compact evidence bundles from sibling workflows, including Telegram `chat_id` / `username` / bounded snippets for a direct contact
- screenshots used as person/relationship evidence, not just identity evidence

The user does not need to invoke a task-template command for this skill to apply.

## Goal

Rapidly evaluate a user-provided set of people candidates without immediately polluting canonical person/company data.

High-level question:
- how useful is it to outreach to these people for Taran.Space business development?

This workflow:
1. stages new/targeted person-candidate records under `scratch/data/people/consider/`,
2. uses `$batch` to manage the per-run scratch task, item iteration, and mandatory staged-review gates,
3. resolves every active current employer against tracked company data,
4. runs `$consider-companies` for every unique active current employer before any canonical company/person promotion, in the same run,
5. evaluates each person's outreach usefulness using the LinkedIn-style buyer/partner/action framework,
6. promotes approved people into canonical person tracking where appropriate,
7. runs `$cache-people` only after canonical person persistence in this workflow,
8. keeps touched tracked companies and people structurally consistent.

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
6. Pass every active current employer through a formal same-run company-resolution step.
   - If the employer is already tracked, invoke `$consider-companies` in tracked-company refresh / review mode rather than relying only on an ad hoc local note.
   - If the employer is not already tracked, invoke `$consider-companies` rather than creating company canon directly.
   - A company-resolution outcome decides whether to use a canonical `{company_id}` reference; it does not decide whether the person can factually list that employer.

## Procedure

1. Prepare the staged person-candidate set and hand the per-run scratch-task lifecycle to `$batch`.
   - Record:
     - `Inputs (verbatim)`
     - `Staging dir`
     - `To process`
     - `Employer resolutions`
     - `Staging -> canonical mapping`
     - `Approved canonical actions`
     - `Persisted people (this run)`
   - The batch source collection is the staged person-candidate set.
   - The scratch task for this run remains one batch scratch task for the whole people-consider run.
2. Stage the explicit person candidates only.
3. Use `$batch` for generic iteration behavior:
   - process only the current batch
   - always show the staged review batch table through `$display-table`
   - default to waiting for user approval after the table
   - even explicit no-pause / auto-approve mode must still display the batch table before applying it
4. Extract profile evidence for each staged person candidate in the current batch.
   - Use the user-provided links/screenshots/exports first.
   - Do brief online research for every active current employer and any materially relevant prior employers when the profile alone does not give enough business context.
   - Record only source-backed fields:
     - full name
     - public profile URL(s)
     - active current role(s)
     - active current employer(s)
     - current-role start month/year when shown for each active role
     - materially relevant prior employers / prior roles
     - location and alternative communication languages when defensible
   - If a profile is too cropped to identify the role/company reliably, ask for an additional screenshot showing the top card plus the current-role block.
   - If the full name is not visible, do not substitute a title like `COO` into the canonical target; ask for a clearer screenshot instead.
   - Keep screenshots and OCR-like extracts in scratch only, never in canonical entities.
5. Resolve every active current employer for each staged person candidate.
   - For every unique active current employer in the batch, create a formal same-run `$consider-companies` outcome exactly once.
   - If an active employer is already tracked:
     - invoke `$consider-companies` in tracked-company refresh / review mode for that employer instead of treating the tracked company as implicitly resolved
     - use the canonical `companies/*.json` entity plus `cache/companies/*.json` to inform that company-consider pass
     - if that company cache is missing/stale/invalid, block on refreshing it before final person promotion
   - If an active employer is not tracked:
     - invoke `$consider-companies` once per unique untracked active employer
     - do not create canonical company or cache files directly from this workflow
   - Wait for the company-consider outcome for every active employer before promoting people tied to that employer.
   - Surface every same-run company-consider result in the people review table under `Company Relevance`, including:
     - the employer name
     - the staged company relevance
     - the company status (`tracked`, `under consideration`, `approved this run`, `not tracked`, or `blocked`)
     - the person whose profile triggered that company-consider handoff
   - Do not replace a company-consider invocation with an ad hoc scratch note, implicit reasoning, or a lightweight one-off company summary.
   - If multiple active current employers are shown concurrently:
     - invoke `$consider-companies` for all of them in the same run; do not stop after the top-card role or the most recent active company
     - keep all source-backed active affiliations in the staged person evidence and final person record if the person is promoted
     - use canonical `{company_id}` refs only for tracked or approved employers
     - use plain company-name strings for real, source-backed employers that were reviewed but not approved for canonical company tracking
     - treat an employer as a blocker only when the employer identity/evidence is unresolved or when omitting/misrepresenting it would make the person record misleading
   - For materially relevant prior employers:
     - use brief research to improve the person's usefulness review
     - do not silently create canonical company tracking from prior-employer context alone
   - If any active current employer does not yet have a formal same-run company-consider outcome, or remains evidence-unresolved:
     - keep the person staged
     - do not silently create canonical company tracking
     - only persist the person independently if the user explicitly approves doing so without the unresolved employer link(s)
   - A company-consider result of `remove` means "do not create/update a canonical company entity"; it does not by itself block person promotion.
     - If the person is promoted, store that active employer as a plain string in `people[].companies[]`.
6. Evaluate outreach usefulness for each staged person candidate.
   - Classify the track:
     - `buyer` if the person works at a protocol/app/exchange/infra team that plausibly buys security work
     - `partner` if the person works at a security firm, dev shop, recruiter/talent agency, advisory, or similar service provider that could refer/subcontract work
     - `unknown` otherwise
   - Evaluate every profile individually; do not ask for a batch-level handling policy for buyers or partners.
   - Use the track to set the business goal for that person's recommendation:
     - `buyer`: the goal is to sell security/design/review services directly
     - `partner`: the goal is to improve mutual deal flow through referrals, subcontracting, overflow help, or adjacent collaboration
     - `unknown`: the goal is to judge whether any outreach path is worth attention yet
   - Choose the recommended action only for LinkedIn/profile-origin candidates:
     - `write immediately`
     - `save for future`
     - `skip, don't spend time`
   - Use `write immediately` only when the person is worth spending outreach attention now, not merely because they accepted a connection request.
     - Strong reasons include product/security ownership, founder/executive/BD authority, a clear buyer pain surface, warm inbound communication, or a specific partner/subcontracting path.
     - A relevant-company employee who is mostly a coverage/routing/community/admin contact should usually be `save for future` after they accept, unless there is a concrete immediate ask that fits their role.
     - If the honest later drafting guidance would be “only write if you want broader company coverage,” do not label the row `write immediately`; label it `save for future` and explain the optional coverage value in `Why`.
     - Accepted connection evidence increases contactability, but it does not by itself make outreach immediate.
     - `save for future` means track in this repo and use the existing LinkedIn/Telegram relationship later; if the person is not connected yet, send a LinkedIn connection request first.
   - For compact evidence bundles from `$telegram-conversations`, omit the `Recommended action` column entirely instead of inventing a Telegram next action. Telegram already proves a message channel exists; the table should focus on persistence, relevance, and blockers.
   - Estimate:
     - `chance (next week)`
     - `chance (6 months)`
   - Use observable signals only:
     - the person’s current role/seniority
     - the active employer set's tracked cache metrics (`summary`, `importance`, `relevance`, `temperature`, `chance_next`, `chance_6m`)
     - prior employers when they materially change business usefulness
     - existing repo communication/context if the person is already tracked
   - Reflect the goal-specific reasoning in the row's `Why` field:
     - for `buyer`, explain why the person looks promising or weak as a direct service buyer
     - for `partner`, explain why the person looks promising or weak for reciprocal deal-flow improvement
   - Keep an internal person-relevance judgement for persistence decisions:
     - if the person is not useful to outreach directly but works at at least one relevant active company, use `1%` as the floor
     - if the person is truly `0%`, do **not** persist the profile canonically
7. Show the staged review batch and stop for approval through `$batch`.
   - Always render the staged review as a Markdown table through `$display-table` that includes the current suggestion for every candidate in the batch, even for single-item batches or when surrounding narrative context is also provided.
   - The table must include a `Blockers` column. Use `none` only when there is no unresolved blocker.
   - If `$consider-companies` was invoked as a sub-step for any employer in the batch, the people review table must reflect that dependency explicitly instead of pretending the employer is fully approved already.
   - If `$consider-companies` was invoked, include the company-consider table or a compact company-decision table in the user-facing response; do not rely only on a scratch-file link.
   - The table must include a `Company Relevance` column for every candidate.
8. Commit the approved batch immediately after approval.
   - `promote`:
     - create/update the canonical person state as approved
     - if a canonical person entity was created or updated, add that person to `Persisted people (this run)`
   - `change`:
     - update the existing canonical person state as approved
     - if a canonical person entity was updated, add that person to `Persisted people (this run)`
   - `remove`:
     - if the item exists only in staging, drop the staged item only
     - if the action removes existing canonical person tracking, require explicit approval and then apply exactly that approved action
9. If `Persisted people (this run)` is non-empty, run `$cache-people` on that set.
   - Because people-cache is currently a stub/no-op surface, this handoff must not block successful person persistence.
   - If this run did not actually persist any canonical person entities, skip the cache step.
10. Validate all touched canonical JSON before finishing.
   - `people/*.json` -> `scripts/validate-people.py`
   - `companies/*.json` when company linkage changed -> `../companies/scripts/validate-companies.py`
   - `cache/companies/*.json` when touched through the company sub-step -> `../../cache/companies/scripts/validate-companies-cache.py`
11. Mark the batch scratch task completed after the final approval gate (or immediately in explicit no-pause mode if there is no blocker).

## Non-negotiable rules

- This workflow must produce a reviewable batch report before canonical changes.
- The staged review report must always include a table with the current suggestion for every candidate in the batch, presented through `$display-table`.
- This workflow uses `$batch` for the generic scratch-task batch loop; keep people-specific evaluation, company-resolution logic, and persistence logic here rather than reimplementing generic batching rules.
- Every considered person must be grounded in explicit profile evidence; do not guess missing current employer/role details.
- Do brief online research for every active current employer and any materially relevant prior employers when needed to evaluate the candidate cleanly.
- Every active current employer must go through a formal same-run `$consider-companies` outcome before canonical company/person promotion, even when the employer is already tracked or is not approved for canonical company tracking.
- Canonical person records may contain multiple current affiliations in `companies[]`; concurrent roles are valid and should be preserved when source-backed.
- Use a canonical `{company_id}` ref only for tracked or approved companies; use a plain company-name string for a real active employer that was considered but not approved for canonical company tracking.
- Use tracked company cache data whenever the employer already exists canonically.
- Do not replace a required `$consider-companies` pass with an ad hoc scratch note or implicit company judgment.
- Do not silently create canonical company tracking from a people-only workflow, whether the signal comes from the current employer or a prior employer.
- All unresolved blockers must be shown in the staged review table's `Blockers` column. Do not present a blocked candidate as unqualified `promote`.
- Do not use `hold` merely because one active employer was reviewed and not approved for canonical company tracking. Prefer `promote` with that employer stored as a plain string unless the employer identity/evidence is unresolved.
- `Relevance: 0%` means the profile must not be persisted canonically.
- `Relevance: 1%` is the floor for “person not directly useful, but at least one active current employer is relevant.”
- New canonical company creation is never allowed directly from this workflow; employer promotion must happen through approved `$consider-companies`.
- Use `$cache-people` only when this workflow actually persisted canonical person entities.
- Never create a brand-new `people/*.json` directly from first-touch intake outside this staged workflow.
- Never bypass staged review because the evidence feels “good enough”.
- Do not edit `aliases.json` unless the user explicitly asked for alias work.
- A direct profile/contact surface is required before clean canonical person registration; a Telegram handle/chat id plus bounded direct-message evidence counts as a contact surface, while evidence-only cases still belong in staged consideration first.
- When multiple concurrent active companies are shown, invoke `$consider-companies` for all of them in the same run before person promotion. If a company is not approved for canonical tracking, keep the affiliation as a plain string unless the evidence is unresolved.
- Do not ask for a batch-level handling policy for buyers or partners; evaluate each profile separately and recommend the best action for that individual's track and business goal.

## Batch report

Use a table with:

`Person` | `Current role(s)` | `Company / companies` | `Company status` | `Company Relevance` | `Track` | `Recommended action` | `Chance (next week)` | `Chance (6 months)` | `Suggestion` | `Blockers` | `Why`

For candidates handed off by `$telegram-conversations`, omit `Recommended action` and use:

`Person` | `Current role(s)` | `Company / companies` | `Company status` | `Company Relevance` | `Track` | `Chance (next week)` | `Chance (6 months)` | `Suggestion` | `Blockers` | `Why`

Where:
- `Person` is the staged candidate's full name
- `Current role(s)` lists all active current roles shown by the evidence; use a concise semicolon-separated summary when there are several
- `Company / companies` lists all resolved active current employers for the person; use a concise semicolon-separated summary when there are several
- `Company status` summarizes the active employer set using per-company labels:
  - `tracked`: canonical company exists and may be referenced as `{company_id}`
  - `approved this run`: canonical company will be created/updated and may be referenced as `{company_id}`
  - `not tracked`: company-consider reviewed it and chose not to create canonical company tracking; if the person is promoted, store this employer as a plain string
  - `under consideration`: company-consider is staged but not yet approved
  - `blocked`: employer identity/evidence is unresolved enough to block an accurate person record
- `Company Relevance` is required for every row:
  - for tracked employers, show each company's current relevance
  - for employers sent through `$consider-companies` in the same run, show each staged company relevance plus the same-run handoff result and the triggering person
- `Track` is one of `buyer`, `partner`, `unknown`
- `Recommended action` is one of `write immediately`, `save for future`, or `skip, don't spend time`; omit this column entirely for `$telegram-conversations` handoffs
  - `write immediately` means this person deserves near-term outreach on their own merits.
  - `save for future` means track the person in this repo and keep the LinkedIn/Telegram route available for later; if they are not in the network yet, send a connection request first.
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
- `Person has active roles at tracked Dedaub and untracked Delalabs; company-consider removes Delalabs` -> if the person is approved, persist `{"company": "{dedaub}", "role": ["BD"]}` and `{"company": "Delalabs", "role": ["COF"]}` in `people[].companies[]`

## Output

When you use this skill, execute the staged people-consider workflow and pass the required approval table to `$display-table` instead of answering with an informal plan.
