---
name: display-people
description: Display one or more people as a concise comparison table. Use for $display-people, people display requests, or asks such as "give me details on these people as a table" including outreach-priority comparisons.
---

# Display People

Display one or many people in a concise, business-facing Markdown table.

This skill is presentation-only. It uses canonical person/company data and current-session context, but it must not create, update, or persist entities. If new people need intake, use `$consider-people` separately.

## Scope

Use this skill when the user asks to display, compare, summarize, or table people, including requests for an `outreach priority` column.

Targets may be:

- canonical person IDs or names,
- LinkedIn profile URLs that resolve to already tracked people,
- same-session people currently being discussed or considered,
- a small explicit set such as "Chris/Shantanu/Sumit".

If a target cannot be resolved to a known person or current-session candidate, ask for the missing data instead of inventing a row.

## Presentation Defaults

Default columns:

| Person | Current role | Company | Background | Latest comms | Outreach priority | Why |
|---|---|---|---|---|---|---|

Adjust columns to the user's request, but keep the table compact and business-facing. Do not expose internal IDs, repo paths, or raw JSON.

Starting-point example for this skill's intended shape:

| Person | Current role | Company | Background | Latest comms | Outreach priority | Why |
|---|---|---|---|---|---|---|
| Chris Moore | Senior Security Researcher | Zokyo | Prior blockchain lead security researcher at Hashlock; broader offensive-security and forensics background. | Accepted LinkedIn request on 18 May; later contacted on LinkedIn. | High | Senior technical profile and a strong route for asking about Zokyo research or audit load. |
| Shantanu Sontakke | Security Researcher | Zokyo | Smart-contract audit background at QuillAudits and Zokyo; also AI-safety side project context. | Accepted LinkedIn request on 18 May. | Medium | Relevant audit partner route, but less senior and no conversation yet. |
| Sumit Kumar | Security Researcher | Zokyo | Smart-contract auditing across Zokyo, QuillAudits, R.E.A.C.H, and OpenSense. | Accepted LinkedIn request on 17 May. | Medium | Useful security-research route, but the profile reads earlier-career. |

## Resolution

1. Resolve explicit names/IDs/URLs against `people/*.json`.
2. For each canonical person, resolve current tracked companies from `"companies"` references and `companies/*.json` display names.
3. If a person is being considered in the current session but is not yet canonical, use only the facts present in the current chat/scratch context and clearly avoid implying persistence.
4. If resolution is ambiguous, ask a concise clarifying question.

Use the same person identity discipline as `$consider-people`, but do not run consideration or persistence logic inside this skill.

## Field Guidance

- `Person`: human-readable name only.
- `Current role`: concise role/title, preferably from current company relation or summary.
- `Company`: current company display name when known; use `-` only when genuinely unknown.
- `Background`: one short sentence, focused on why the person matters.
- `Latest comms`: latest meaningful communication or LinkedIn connection-state summary; include a friendly date when known.
- `Outreach priority`: `High`, `Medium`, or `Low`.
- `Why`: the tactical reason behind the priority, not a biography.

Priority guidance:

- `High`: senior or decision-adjacent, directly relevant, responsive/contacted, or a strong route to active work.
- `Medium`: relevant but accepted-only, less senior, or useful mostly as a secondary route.
- `Low`: weak role fit, stale/uncontactable, or not useful for the current outreach goal.

Connection-state guidance:

- Accepted or added LinkedIn state is useful contactability, but not responsiveness.
- Trivial greetings do not by themselves make someone responsive.
- If the user asks who to message next, do not recommend people who are only `Tracked` unless the user explicitly asks for connection-request targets.

## Output

- Assemble one Markdown table, then pass it to `$display-table`.
- A display task is incomplete until `$display-table` has shown the table in chat or opened it externally.

## Non-Negotiables

- Do not mutate `people/*.json`, `companies/*.json`, `cache/companies/*.json`, or `aliases.json`.
- Do not trigger `$consider-people`; only mention it if intake is needed.
- Do not store outreach recommendations or table summaries as canonical data.
