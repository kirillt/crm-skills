---
name: consider-companies
description: Stage organization-first intake through the company consideration workflow. Use when the input contains company/homepage URLs, LinkedIn company pages, GitHub orgs, docs sites, product/protocol/network names used as organizations, or other organization evidence that may lead to canonical company persistence. This skill owns company-side staged review logic, canonical finalization, and post-approval handoff to `$cache-companies`, while using `$batch` for the generic scratch-task batch loop.
---

# Consider Companies

## Overview

Route company-first intake into the staged company consideration workflow before canonical persistence.

Use this skill for new or unresolved companies, products, protocols, and networks that might become canonical company targets.

## Trigger Conditions

Use this skill when the input could cause a brand-new company-like entity to be tracked canonically, including:
- an official company/homepage URL
- a LinkedIn company page
- a GitHub org, docs site, or product/protocol/network surface used as an organization
- a company/product/protocol/network name used as a potential tracked organization
- organization evidence about staff, products, audits, relationships, or business relevance
- compact evidence bundles from sibling workflows, including Telegram `chat_id` / `username` / bounded snippets that identify an organization surface

The user does not need to invoke a task-template command for this skill to apply.

## Goal

Rapidly evaluate a user-provided set of company candidates without immediately polluting canonical company data.

This workflow:
1. stages new/targeted company-candidate records under `scratch/data/companies/consider/`,
2. uses `$batch` to manage the per-run scratch task, item iteration, and mandatory staged-review gates,
3. runs a staged version of the canonical company refresh procedure on only that set,
4. promotes approved companies into canonical company/relationship tracking where appropriate,
5. finalizes approved canonical company state directly inside this workflow,
6. refreshes cache semantics via `$cache-companies` only when this run actually persisted canonical company entities,
7. optionally performs a founder / decision-maker online-search pass only after the user explicitly approves that extra step.

When this workflow needs to decide whether a company is relevant to our business or which rubric IDs apply, load the policy stack in this order:
- `about-us/intro.md` for positioning and pricing context
- `about-us/leads-qualification.md` for relevance/importance/chance/temperature semantics
- `about-us/rubrics.py` for canonical rubric IDs, weights, and deterministic scoring helpers

## Decision Rule

Treat these as company-side signals:
- official company/homepage URLs
- LinkedIn company pages such as `linkedin.com/company/...`
- GitHub orgs, docs sites, product/company names used as organizations
- evidence about staff, products, audits, relationships, or business relevance of an organization

Use best judgement for ambiguous text:
- if the item is primarily “should we track this organization?” treat it as company intake
- when the input is a product/protocol/network, resolve whether the actionable business surface is the product itself or an owner / umbrella company
- if the legal/operator company is unknown but the product/protocol/network is itself the practical buyer, employer, public brand, or relationship surface, use that public name as the staged canonical target and do not block only on missing legal-name discovery

## Procedure

1. Prepare the staged company-candidate set and hand the per-run scratch-task lifecycle to `$batch`.
   - Record:
     - `Inputs (verbatim)`
     - `Staging dir`
     - `To process`
     - `Staging -> canonical mapping`
     - `Approved canonical actions`
     - `Persisted companies (this run)`
   - The batch source collection is the staged company-candidate set.
   - The scratch task for this run remains one batch scratch task for the whole company-consider run.
2. Stage the explicit company candidates only.
   - If the input is a Telegram evidence bundle, preserve the bundle path/ids in staging and use the provided snippets first; do not rescan Telegram cache unless the bundle is insufficient.
3. Use `$batch` for generic iteration behavior:
   - process only the current batch
   - always show the staged review batch table through `$display-table`
   - default to waiting for user approval after the table
   - even explicit no-pause / auto-approve mode must still display the batch table before applying it
4. Run the semantic review logic from `tasks/companies/refresh.md` in staged mode for the current batch.
   - For already tracked companies: this is a normal company refresh.
   - For new company candidates: use the same official-link research and canonical-model checks, but keep the result staged until approval.
   - Track only candidates that are relevant to our business.
   - Read `about-us/leads-qualification.md` before choosing rubric IDs or interpreting relevance/chance/temperature.
   - Use `about-us/intro.md` to keep staged decisions aligned with current positioning and flagship case-study emphasis.
   - When scoring chosen rubric IDs, invoke `about-us/rubrics.py` instead of parsing or duplicating rubric weights:
     - `.venv/bin/python about-us/rubrics.py --list`
     - `.venv/bin/python about-us/rubrics.py --rubrics web3_security --transitive-rubrics cryptographic_proofs`
   - When the input is a product/protocol/network, resolve whether the actionable business surface is the product itself or an owner / umbrella company.
   - If the owner / umbrella company is known and the narrower product surface is not independently useful, resolve the candidate to the owner / umbrella company instead of creating a separate canonical record.
   - For every reviewed item, record a staged-to-canonical resolution:
     - input / staged candidate
     - resolved canonical company target, if any
     - whether the item stays separate, merges into an existing company, or should be removed
5. Before each staged approval gate, do a best-effort LinkedIn lookup for each reviewed company candidate.
   - Search for the official website and official company LinkedIn page at minimum.
   - Also record other official surfaces when found (for example GitHub, X/Twitter, docs).
   - Use the resolved company name, even if the original input was a URL.
   - Prefer the official company LinkedIn page when there is a unique defensible match.
   - If online research is inconclusive, continue only with an explicit blocker in the staged review table and in the run's research notes.
6. Show the staged review batch and stop for approval through `$batch`.
7. Finalize the approved batch immediately after approval.
   - Resolve canonical company targets by exact match, aliases, or a unique typo-tolerant normalized match.
   - Run a mandatory deduplication check before any canonical write:
     - foundation/lab/operator/company vs protocol/brand/product
     - product/network vs owner / umbrella company
     - app/product vs builder/legal entity
   - Before canonical promotion, ensure there is enough source-backed company evidence to support cache refresh:
     - official website when found
     - what they ship / the practical business surface
     - GitHub org/repo when applicable
     - security intake surface when available
   - Before finalizing a `promote` outcome for a company that did not previously exist canonically, run a plain-affiliation reconciliation pass:
     - scan `people/*.json` for exact plain-text matches to the approved company display name and obvious approved spelling variants in both `companies[*].company` and `past_career[*].company`
     - for current-company matches, convert the person record to the canonical `{company_id}` reference and add the tracked person to company `staff` with the best source-backed role code
     - for past-career matches, convert the person record to the canonical `{company_id}` reference and prepare cache `former_staff_routes` entries after cache creation/refresh
     - include these reconciled people in the run's validator set and final summary
   - Commit approved outcomes:
     - `promote`:
       - create/update canonical company state as approved
       - persist every clear official link found
       - persist the staged canonical target after any owner/operator resolution
       - add the company to `Persisted companies (this run)`
     - `change`:
       - update the existing canonical company state as approved
       - add the touched company to `Persisted companies (this run)`
     - `remove`:
       - if the item exists only in staging, drop the staged item only
       - if the action removes, merges, or renames existing canonical company tracking, require explicit approval and then apply exactly that approved action
       - when this run was invoked by `$consider-people`, a `remove` outcome means the company should not become a canonical `companies/*.json` entity; it does not prohibit a promoted person from listing that employer as a plain company-name string
   - Record the committed outcomes under `Approved canonical actions`.
8. If `Persisted companies (this run)` is non-empty, run `$cache-companies` on that set.
   - If this run did not actually persist any canonical company entities, skip the cache step.
9. Mark the batch scratch task completed after the final cache-review gate (or immediately in explicit no-pause mode if there is no blocker).
10. Optional post-completion follow-up:
   - only if the user explicitly approves this extra step after the required task work is already complete, do a best-effort online search for founders and decision makers of the approved companies
   - this is not part of the required completion path

## Non-negotiable rules

- This workflow must produce a reviewable batch report before canonical changes.
- The staged review report must always include a table with the current suggestion for every candidate in the batch, presented through `$display-table`.
- This workflow uses `$batch` for the generic scratch-task batch loop; keep company-specific scoring, research, and persistence logic here rather than reimplementing generic batching rules.
- Every considered company must go through online research before the staged review table is shown. At minimum, attempt official website and official LinkedIn lookup; record attempted-but-inconclusive research.
- Track only companies/products/protocols/networks that are relevant to our business.
- Use the about-us policy stack when making that relevance judgement:
  - `about-us/intro.md` for positioning context
  - `about-us/leads-qualification.md` for scoring semantics
  - `about-us/rubrics.py` for rubric IDs/weights
- When the candidate is a product/protocol/network, choose the canonical target based on the real business surface: keep the product/protocol/network when it is independently actionable, otherwise prefer the owner / umbrella company.
- All unresolved blockers must be shown in the staged review table's `Blockers` column. Do not present a blocked candidate as unqualified `promote`.
- Structural/destructive changes require explicit user approval unless explicit no-pause mode was requested and the batch is unambiguous.
- Before recording a new company entity canonically, do best-effort online research for official primary surfaces and persist every clear official link found. At minimum, attempt official website and official LinkedIn lookup.
- Before recording a new company entity canonically, reconcile existing plain-text people affiliations for the approved company name; do not leave known current staff or former-staff routes stranded under the old plain string.
- New canonical company creation is allowed only through this workflow’s explicit approval gate; do not bypass it from sibling skills or tasks.
- This workflow owns canonical finalization for approved companies; do not route approved-company persistence through a separate register template.
- Use `$cache-companies` only when this workflow actually persisted canonical company entities.
- Validate touched canonical company files with `scripts/validate-companies.py`.
- Keep staging-only removals out of canonical company tracking until approval.
- A `remove` decision for a company candidate means no canonical company record should be created or updated for that organization. It does not prohibit storing that organization as a plain string in a person's current or past affiliations.
- The staged review batch must include the staged-to-canonical resolution so the user can verify what each input really maps to before canonical writes happen.
- Once a batch is approved, commit that approved set immediately to canonical entities/cache-follow-up state; do not silently rewrite that approved batch later.
- Founder / decision-maker online search is optional and must never block task completion.
- Never create a brand-new `companies/*.json` directly from first-touch intake outside this staged workflow.
- Do not edit `aliases.json` unless the user explicitly asked for alias work.

## Batch report

Use a table with:

`Input` | `Canonical target` | `Rubrics` | `Relevance` | `Suggestion` | `Blockers` | `Summary`

Where:
- `Input` is the user-provided / staged candidate name
- `Canonical target` is the company that would actually be written or updated if approved
- `Rubrics` lists the canonical rubric IDs that produce the relevance score, or `none` when relevance is `0%`
- `Blockers` lists unresolved issues that block or condition canonical changes; use `none` only when no blocker remains

## Examples

- `https://kyve.foundation` -> staged company-consider
- `One company URL and one company LinkedIn page for the same organization` -> deduplicate, then staged company-consider
- `A product/protocol URL with no clear legal entity yet` -> staged company-consider with public brand resolution

## Output

When you use this skill, execute the staged company-consider workflow and pass the required approval table to `$display-table` instead of answering with an informal plan.
