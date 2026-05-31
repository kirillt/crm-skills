---
name: outreach-people
description: Rank one or more known people as outreach targets in a compact table. Use when the user explicitly invokes `$outreach-people`, asks which people are worth outreach, asks to rank people for sales or partner outreach, or wants a person-level outreach table with response and project chances.
---

# Outreach People

Rank known people as outreach targets.

This skill is presentation-only. It uses canonical person/company data and current-session context, but it must not create, update, or persist entities. If new people need intake, use `$consider-people` separately.

## Scope

Use this skill when the user asks to rank, compare, prioritize, or table people for outreach, especially with sales/partner angles or response/project chances.

Targets may be:
- canonical person IDs or names,
- LinkedIn profile URLs that resolve to already tracked people,
- same-session people currently being discussed or considered,
- an explicit small set such as "Alice/Bob/Carol".

If a target cannot be resolved to a known person or current-session candidate, ask for the missing data instead of inventing a row.

## Data Sources

Use the minimum needed current context:
- `people/*.json` for person identity, roles, contactability, and communication history.
- linked `companies/*.json` for current tracked employers and staff roles.
- `cache/companies/*.json` for company `importance`, `temperature`, `chance_next`, `chance_6m`, contacts, and latest comms.
- `about-us/leads-qualification.md` when company scoring semantics are needed.

Do not read `state/outreach/style.json`; this skill ranks targets, it does not draft messages.

## Evaluation

For each person, determine:
- `Role`: concise current role code or human-readable role, preferably from the person/company relation.
- `Person`: format as `Name @ Company`; use `Name @ -` only when company is genuinely unknown.
- `Worthiness of outreach`: outreach importance plus chance of response, formatted as `<Top|High|Medium|Low> <zz%>`.
- `Angle`: `Sales`, `Partner`, or `Unknown`.
- `Project chance`: chance to get a project in `1w/6mo`, formatted as `xx%/yy%`.

Angle guidance:
- `Sales`: the person works at a protocol, app, exchange, infra team, fund, or other organization that could directly buy security/design/review work.
- `Partner`: the person works at a security firm, dev shop, recruiter/talent agency, advisory, ecosystem, or similar route that could refer, subcontract, or improve deal flow.
- `Unknown`: the role/company context does not cleanly support either goal.

Worthiness guidance:
- `Top`: senior or decision-adjacent, strong company fit, strong contactability or communication, and a plausible near-term ask.
- `High`: relevant and reachable, with a credible sales or partner reason.
- `Medium`: useful but weaker due to role distance, accepted-only contactability, lower company fit, or no clear immediate ask.
- `Low`: weak role fit, stale/uncontactable, unknown company relevance, or little practical business path.

Chance guidance:
- `Chance of response` is person-level: use contact state, latest communication, channel availability, relationship warmth, and role fit.
- `Project chance` is opportunity-level: start from tracked company cache `chance_next` and `chance_6m` when available, then adjust only when the person's role materially changes access to the opportunity.
- If no company cache exists, estimate conservatively from observable person/company context and say so briefly above the table.
- Keep percentages as whole-number percent strings.

## Sorting

Sort rows by:
1. `Worthiness of outreach` rank: `Top`, `High`, `Medium`, `Low`.
2. `Project chance` 1w value, descending.
3. `Project chance` 6mo value, descending.
4. Chance of response, descending.
5. Person name, ascending.

## Output

Assemble exactly this Markdown table and pass it to `$display-table`:

| Role | Person | Worthiness of outreach | Angle | Project chance |
|---|---|---|---|---|
| CTO | Alice Smith @ Example Labs | Top 65% | Sales | 12%/45% |

If more than one current company is material, use the best outreach target company in `Person` and mention the other company only if needed in the row's role or a short note above the table.

## Non-Negotiables

- Do not mutate `people/*.json`, `companies/*.json`, `cache/companies/*.json`, `aliases.json`, or `state/outreach/style.json`.
- Do not trigger `$consider-people`; only mention it if intake is needed.
- Do not draft messages.
- Do not store outreach recommendations or table summaries as canonical data.
- Do not expose internal IDs, repo paths, raw JSON, or machine-styled scoring fields in the final table.
