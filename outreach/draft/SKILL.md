---
name: outreach-draft
description: Draft short outbound outreach messages for one or several people whose profiles are already persisted or are being considered in the current session, and record actually sent outbound messages when the user provides the sent text. Use when the user asks to write or draft a message to someone, explicitly invokes `$outreach-draft`, or reports that an outbound message was sent. Always use `state/outreach/style.json` for drafting, and invoke `$outreach-adjust` after sent-message tracking.
---

# Outreach Draft

## Overview

Use this skill when the user explicitly wants an outbound message draft for one or more people, or when the user reports that an outbound message was actually sent.

This skill owns the normal outreach loop:
- draft from persisted or same-session-considered person context
- when the user later provides the actual sent message, track the communication
- update company cache when the communication changes cache-facing state
- invoke `$outreach-adjust` after tracking so real sent wording can refine `state/outreach/style.json`

Do not create scratch tasks for this workflow.
`state/outreach/style.json` is the drafting style dependency and must always be read before finalizing message wording.
`$outreach-adjust` is the only skill that may change the stored style JSON.

## Trigger Conditions

Use this skill when:
- the user asks to write or draft a message to someone
- the user asks for a reply draft to a known contact
- the user explicitly invokes `$outreach-draft`
- the user reports that an outbound message was sent and provides enough detail to track it

Do not use this skill for inbound-message tracking by itself; keep the normal communication-persistence workflow intact.

## Scope Rules

- Every person in scope must already be:
  - persisted in `people/*.json`, or
  - under active same-session consideration through `$consider-people`
- Their current companies must already be:
  - persisted in `companies/*.json`, or
  - under active same-session consideration through `$consider-companies`
- Draft targets must be people, not companies. If the user names a company/team, ask them to select the person first using the appropriate people/company display or consideration workflow.
- If the needed person or company context is missing, stop and route through the appropriate consideration workflow first.
- Sent-message recording requires the actual sent text or a clear user-confirmed summary, channel/app, send date, and recipient. If any of these are missing, ask for the missing fields before editing.

## Inputs

- If the input is empty:
  - use the last mentioned people in the current session, newest first
  - include at most 5 people
  - if more than 5 candidates qualify, say that the scope was truncated to the latest 5
- If the input is non-empty:
  - interpret it as person references from the session or disk
  - allow exact IDs, names, profile URLs, and obvious same-session references that resolve to one person
  - collapse duplicates before drafting

## Procedure

### Draft Mode

Use this mode when the user asks for wording and has not confirmed a sent message.

1. Resolve the target people.
   - Prefer same-session considered people first.
   - Then check persisted `people/*.json`.
   - Use the linked company context from persisted company files, company cache, or same-session company-consider output.
2. If any target person or active company context is unresolved, stop and say which target must be persisted or considered first.
3. Gather the minimum drafting context for each person:
   - relationship state and latest meaningful communication
   - current role and company
   - what that role likely cares about in practice
   - 1-2 company-specific details that matter to our business positioning
   - 1-2 role-specific details that make the outreach angle credible for that person
   - language preference if explicitly tracked
4. Read `state/outreach/style.json` as a required dependency before finalizing wording.
   - Use its current rules and best examples as the default style prior.
   - Consume the style JSON in read-only mode only.
   - Do not mutate the style JSON during normal drafting.
   - If the user supplied extra style guidance in this turn, combine it with the stored style rather than replacing it.
5. Draft one best message per person.
   - Follow `state/outreach/style.json` for voice, length, close, and banned phrasing.
   - Use only specific details that are true for that person and relevant to our business.
   - Tailor the angle to the person's actual role and the company's actual business surface, not just the company name.
   - Make the relevance legible from the recipient's perspective: why this person, at this company, would care now.
6. Return the result in the required output shape.

### Sent-Message Recording Mode

Use this mode when the user reports that an outbound message was actually sent.

1. Resolve the recipient person and involved company.
   - If the recipient is not tracked or under same-session consideration, route through `$consider-people` before recording.
   - If the company is not tracked or under same-session consideration, route through `$consider-companies` before company-side recording.
   - If the recipient has a known tracked company, ensure the person is represented under that company's `"staff"` when current-company evidence supports it.
2. Confirm required tracking inputs.
   - Required: actual sent text or a clear user-confirmed summary, channel/app, send date, and recipient.
   - Dates must be exact `YYYY-MM-DD`.
   - If the user gives a past date without a year, infer the latest possible year that is not in the future.
   - If date/channel/recipient is unclear, ask for the missing data before editing.
3. Persist communication summaries, not verbatim sent text.
   - Add a dated `"comms.events"` item to the recipient's `people/*.json`.
   - Add or update the same dated `"comms.events"` day summary in the relevant `companies/*.json` when the message is company-level or company-relevant.
   - Store app/channel in `where`; store introducer, routing, or business context in `summary`.
   - Do not store the verbatim message body in canonical people or company entities.
4. Validate touched canonical files.
   - Run `.agents/skills/consider/people/scripts/validate-people.py` for touched people.
   - Run `.agents/skills/consider/companies/scripts/validate-companies.py` for touched companies.
   - Write validator status under `logs/validators.log/`.
5. Re-check company cache when a company was touched.
   - Consider `temperature`, `latest_comms`, `latest_comms_date`, `chance_next`, and `chance_6m` using `about-us/leads-qualification.md`.
   - Run `$cache-companies <company>` when the new communication changes cache-facing state or when cache needs to mirror the latest communication.
   - If no cache update is needed, explain the no-change decision in chat.
6. Invoke `$outreach-adjust`.
   - Pass the actual sent text and any matched draft context from the current conversation.
   - Let `$outreach-adjust` decide whether and how to update `state/outreach/style.json`.
7. Return a concise confirmation of what was tracked and whether cache/style changed.

## Drafting Rules

- Follow `state/outreach/style.json` as the outreach style source of truth.
- Never claim a prior relationship or meeting unless it is explicitly tracked.
- If replying to a direct question or a warm intro, answer that question first.
- The draft must account for both:
  - the target's role, incentives, and likely decision surface
  - the company's specific product, protocol, service, or operating context
- Do not send the same generic company-level pitch to different roles at the same company; adjust the angle to the recipient.
- Default to English unless a different preferred language is explicitly tracked.
- Return one best draft, not variants, unless the user asks for alternatives.

## Output

- If only 1 person is in scope:
  - return only the draft message
- If more than 1 person is in scope:
  - assemble a Markdown table with exactly 2 columns and pass it to `$display-table`:
    - `Name`
    - `Draft`

When you use this skill, either return the actual draft(s) or complete the sent-message tracking flow, including cache follow-up and `$outreach-adjust`.
