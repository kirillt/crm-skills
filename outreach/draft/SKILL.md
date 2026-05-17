---
name: outreach-draft
description: Draft short outbound outreach messages for one or several people whose profiles are already persisted or are being considered in the current session, with company context available. Use when the user asks to write or draft a message to someone, or explicitly invokes `$outreach-draft`. Always use `state/outreach/style.json` to tailor the wording before returning the final draft.
---

# Outreach Draft

## Overview

Use this skill when the user explicitly wants an outbound message draft for one or more people.

This skill is the drafting surface.
`state/outreach/style.json` is the read-only style dependency and must always be used before finalizing the message wording.
`$outreach-adjust` is the only skill that may change the stored style JSON.

## Trigger Conditions

Use this skill when:
- the user asks to write or draft a message to someone
- the user asks for a reply draft to a known contact
- the user explicitly invokes `$outreach-draft`

Do not use this skill for inbound-message tracking by itself; keep the normal communication-persistence workflow intact.

## Scope Rules

- Every person in scope must already be:
  - persisted in `people/*.json`, or
  - under active same-session consideration through `$consider-people`
- Their current companies must already be:
  - persisted in `companies/*.json`, or
  - under active same-session consideration through `$consider-companies`
- If the needed person or company context is missing, stop and route through the appropriate consideration workflow first.

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
   - Keep it short: usually 1-2 sentences.
   - Use only specific details that are true for that person and relevant to our business.
   - Tailor the angle to the person's actual role and the company's actual business surface, not just the company name.
   - Make the relevance legible from the recipient's perspective: why this person, at this company, would care now.
   - Default to one clear idea, not a mini-pitch deck.
6. Return the result in the required output shape.

## Drafting Rules

- Follow the repo outreach guardrails from `AGENTS.md`.
- Never claim a prior relationship or meeting unless it is explicitly tracked.
- If replying to a direct question or a warm intro, answer that question first.
- Use 1-2 concrete credibility facts at most when they genuinely help.
- The draft must account for both:
  - the target's role, incentives, and likely decision surface
  - the company's specific product, protocol, service, or operating context
- Do not send the same generic company-level pitch to different roles at the same company; adjust the angle to the recipient.
- Avoid filler such as “we help”, “happy to connect”, “quick call”, “no pitch”, or generic compliments.
- Default to English unless a different preferred language is explicitly tracked.
- Default to a permissionless close; include one low-friction question only when it helps.
- Return one best draft, not variants, unless the user asks for alternatives.

## Output

- If only 1 person is in scope:
  - return only the draft message
- If more than 1 person is in scope:
  - return a markdown table with exactly 2 columns:
    - `Name`
    - `Draft`

When you use this skill, resolve the people, apply `state/outreach/style.json`, and return the actual draft(s) instead of an informal plan.
