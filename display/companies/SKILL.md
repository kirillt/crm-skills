---
name: display-companies
description: Render focused company tables from current company cache data. Use for $display-companies, legacy \companies\display requests, or company display requests over explicit company names, company collections, or company rubric expressions.
---

# Display Companies

Render a focused company table for an explicit subset.

This skill is display-first. It must not create new canonical entities or update cache/scoring data. It may perform narrow semantic-preserving communication sync between already-tracked `people/*.json` and `companies/*.json` records when required by the bidirectional communication rules below.

## Invocation

Use this skill for:

- `\companies\display <company names...>`
- `\companies\display <rubric_expr>` where the single positional argument is wrapped in `<...>`
- `\companies\display -<rubric_expr>`
- `\companies\display --collection cache/lists/collection-<slug>-<YYYYMMDD-HHMMSS>.json`
- `\companies\display <...> --sort <top|queue>`
- `\companies\display <...> --preserve-order`
- `$display-companies ...`

## Arguments

- `company_names`: semicolon-separated company names, IDs, or aliases.
- `rubric_expr`: a company subset expression that must be resolved through `$companies-list`.
- `collection`: an existing collection JSON under `cache/lists/`.
- `sort`: `top` by default, or `queue` for relationship/recency-oriented ordering.
- `preserve-order`: keep collection order exactly as provided.

## Rules

- If neither explicit company names nor `--collection` is provided, stop and tell the user to use global views such as `\leads\top` or `\leads\queue`.
- `Groups` (`RLNT`) are local by default: compute them from the displayed subset only.
- Do not show internal IDs, cache filenames, or repo paths in the rendered business-facing table.
- Always append a people/status table for the displayed company subset, whether the subset contains one company or many.
- The people/status table is owned by this skill; do not delegate to `\people\list`.
- For a single displayed company, render people as `Name`.
- For multiple displayed companies, render people as `Name @ Company`.
  - If one person belongs to more than one displayed company, render `Name @ Company A / Company B`.
- Deduplicate people across the displayed subset.
- Do not show people whose only relationship to the displayed subset is a non-current past employer.

## People Status Table

After the company table, append one Markdown table grouping all people in the displayed subset into status columns:

`Stub` | `Tracked` | `Added` | `Accepted` | `Contacted` | `Responsive`

Skip empty columns. Each person must occupy a dedicated table row; do not combine multiple people in one cell.

Statuses:
- `Stub`: staff mention without an actionable canonical person profile.
- `Tracked`: profile is persisted and has a role/profile surface, but no direct contactability or non-trivial direct interaction is recorded.
- `Added`: they sent Kirill a LinkedIn connection request and Kirill accepted; no richer direct interaction is recorded.
- `Accepted`: they accepted Kirill's LinkedIn connection request; no richer direct interaction is recorded.
- `Contacted`: non-trivial direct outreach or interaction is recorded, but the latest meaningful state is not clearly responsive.
- `Responsive`: the latest meaningful interaction state is responsive, or the person was responsive and our later message does not reasonably require a reply.

Contactability and communication interpretation:
- LinkedIn `Added` / `Accepted` is trivial contactability; it does not by itself count as `Contacted` or `Responsive`.
- Deterministic scripts may gather candidate people, exact dates, latest-event ordering, and whether the latest message is before or within a responsiveness threshold.
- Deterministic scripts must not classify semantic statuses such as `Contacted` vs `Responsive` by keyword heuristics.
- Use LLM judgment over the actual canonical communication summaries to decide:
  - whether a communication is non-trivial or only a greeting/connection artifact;
  - whether the latest meaningful event is inbound-responsive, outbound-only, mixed, or closed;
  - whether our latest outbound message reasonably expected a reply;
  - whether a company-side group/thread event is person-specific enough to count for that person.
- If the latest meaningful interaction is inbound from them, classify `Responsive`.
- If the latest meaningful interaction is ours and within the responsiveness threshold, keep `Responsive` when they were previously responsive; otherwise classify `Contacted`.
- If the latest meaningful interaction is ours and before the responsiveness threshold, downgrade from `Responsive` only when that message reasonably expected a reply.
- If our latest message closed/confirmed/agreed/shared information and did not require a reply, do not downgrade them solely because no later reply exists.

Person/company communication sync:
- Company-relevant 1:1 communication must be represented bidirectionally:
  - `people/<person>.json` under `"comms.events"`;
  - `companies/<company>.json` under `"comms.events"`.
- If display preparation finds person-side company-relevant communication missing from the company record, treat it as a company sync gap.
- If display preparation finds company-side person-specific communication missing from the person record, treat it as a person sync gap.
- Semantic-preserving sync is allowed without extra approval; any merge, removal, reduction, or reinterpretation of persisted communication content requires caution and, when content would be reduced, explicit user confirmation.
- For group chats/threads, company-side history may summarize the group/company thread, but person-side history should be added only for people who actually interacted or received person-specific follow-up.
- The rendered people/status table should classify from synchronized canonical records. If a sync gap cannot be safely fixed during the display run, report the gap clearly instead of silently downgrading status.

## Benchmark Groups

This skill owns benchmark-group (`RLNT`) display semantics together with its renderer in `.agents/skills/display/companies/scripts/companies-display.py`.

- `R_seed`: sort by higher `relevance`, then higher `chance_6m`, then higher `chance_next`, then higher temperature rank, then alphabetical company; take the top 10.
- `L_seed`: sort by higher `chance_6m`, then higher `chance_next`, then higher temperature rank, then higher `relevance`, then alphabetical company; take the top 10.
- `N_seed`: sort by higher `chance_next`, then higher `chance_6m`, then higher temperature rank, then higher `relevance`, then alphabetical company; take the top 10.
- `T_seed`: sort by higher temperature rank, then higher `chance_next`, then higher `chance_6m`, then higher `relevance`, then alphabetical company; take the top 10.
- Expand each letter by metric equality with its seed set, so groups may grow beyond 10 entries.
- Display letters in canonical order `RLNT`, or `(none)` if absent.
- For explicit display subsets, compute groups from the displayed subset only unless the calling task explicitly defines a global view.

## Procedure

1. Resolve the target company set.
   - Explicit company names: resolve to canonical `companies/*.json` IDs and write a deterministic collection JSON under `cache/lists/` with `python3 .agents/skills/companies/list/scripts/companies-resolve.py`.
   - Single rubric/topic expression: resolve it with `$companies-list`, then use the resulting collection JSON.
   - `--collection`: reuse the given collection JSON.
2. Render deterministically with:
   - `python3 .agents/skills/display/companies/scripts/companies-display.py --mode display --collection <collection_path> --stdout`
   - add `--sort queue` when requested.
   - add `--preserve-order` when requested.
3. Build the people/status table for the displayed subset.
   - Parse each displayed `companies/<id>.json` `"staff"` list.
   - Scan `people/*.json` for `"companies[*].company"` references to displayed companies.
   - Union and deduplicate candidates.
   - Read each involved canonical person record and the displayed company records' `"comms.events"`.
   - Check bidirectional communication sync for company-relevant 1:1 interactions.
   - Apply the People Status Table rules above using LLM judgment for semantic status classification.
4. Assemble the final output.
   - Company table, then a blank line, then the merged people/status table.
5. Pass the assembled Markdown table output to `$display-table`.
   - If there is no transformation needed, a pre-rendered Markdown file may be passed directly to `$display-table`.
   - If the people/status table is assembled outside the Python renderer, perform that transformation in memory or in a new output file; never edit an input renderer file.
   - `$display-table` owns the final chat-vs-file/viewer routing.

## Output

- Markdown table using the shared `display` company-table contract defined in `.agents/skills/display/companies/scripts/companies-display.py`.
- The renderer contract is the source of truth for exact company columns, including optional `Position` behavior for multi-company outputs.
- `Latest communication` is included only when `--sort queue`.
- Always append the merged people/status table immediately after the company table.
- Final presentation is handled by `$display-table`.

## Non-Negotiables

- Do not let the Python renderer be the whole output; the result is incomplete unless the merged people/status table is appended.
- Do not use keyword heuristics to decide whether a person is `Contacted` or `Responsive`; use LLM interpretation of canonical communication summaries.
- Do not mutate canonical or cache data except for narrow semantic-preserving person/company communication sync explicitly allowed above.
