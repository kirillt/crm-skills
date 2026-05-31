---
name: companies-list
description: Resolve company subset requests into a concrete tracked-company list. Use when the user explicitly invokes `$companies-list`, or when company-facing tasks need to expand semicolon-separated company selectors, canonical subset expressions like `<l1_l2>` or `-<...>`, or freeform `<...>` chat-context selectors into a deterministic company set.
---

# Companies List

## Overview

Use this skill to expand company subset requests into a concrete company list.

This skill is the source of truth for behavior that used to be split between:
- `\companies\query`
- AGENTS-level angle-bracket selector rules for company list tasks

This skill operates on:
- `companies/*.json`
- `aliases.json`
- `about-us/rubrics.py`
- `.agents/skills/companies/list/scripts/companies-query.py`
- `.agents/skills/companies/list/scripts/companies-resolve.py`

## When To Use

Use this skill when:
- the user invokes `$companies-list`
- a company-facing task needs a concrete company subset from a semicolon-separated selector list
- a company-facing task receives one `<...>` item and must decide whether it is a subset expression or a freeform chat-context selector

Typical callers:
- `$display-companies`
- `\companies\refresh`
- `\leads\top`

## Input Kinds

This skill supports three input kinds:

1. Explicit company selectors
   - semicolon-separated company names / ids / aliases
   - example: `Matter Labs; Cyberscope; Hashlock`

2. Canonical subset expressions
   - `<...>` expressions
   - negated `-<...>` expressions
   - operators:
     - `/` = OR
     - `&` = AND
     - ` - ` = set difference

3. Freeform `<...>` company selectors from chat context
   - multi-word `<...>` input with no operators and not a clear canonical expression
   - expand it into a concrete company list using current chat context
   - if expansion is empty or ambiguous, stop and ask

## Resolution Rules

### Explicit company selectors

1. Resolve semicolon-separated company names / ids / aliases into canonical company ids.
2. Use deterministic explicit-list resolution via `.agents/skills/companies/list/scripts/companies-resolve.py`.
3. Deduplicate while preserving deterministic order.

### Canonical subset expressions

1. If the user already provided a strict canonical rubric expression, keep it as-is.
2. If the user used loose human wording, resolve it into canonical rubric ids from `about-us/rubrics.py`.
3. Then expand it deterministically with `.agents/skills/companies/list/scripts/companies-query.py`.

Examples:
- `security vendors` -> `<web3_security/security_vendor>`
- `L1 or L2` -> `<l1_l2>`
- `wallet companies` -> `<wallets>`
- `cross-chain & Rust` -> `<cross_chain & rust>`

### `<...>` interpretation rule

When the input is exactly one `<...>` item:

- treat it as a canonical subset expression if the inner text:
  - contains `/`, or
  - contains `&`, or
  - contains a whitespace-surrounded ` - ` operator, or
  - contains no whitespace
- otherwise treat it as a freeform chat-context selector and expand it from current context

## Output Modes

### Direct mode

When the user explicitly invokes `$companies-list`, output exactly:

- `Count: <N>`
- `Companies: <CompanyA; CompanyB; ... | (none)>`

Rules:
- use human-readable company names from `companies/*.json`
- sort companies alphabetically, case-insensitive
- deduplicate
- if no companies match, return `Count: 0` and `Companies: (none)`

### Helper mode

When another task uses this skill as a sub-step:
- expand to a concrete deterministic company set
- preserve canonical company ids for the caller’s internal work
- produce a collection file when the caller needs one
- do not add extra explanatory prose unless the resolution was ambiguous or blocked

## Non-negotiable Rules

- Use canonical `companies/*.json` as the source of truth for subset membership.
- Do not use cache as the source of truth for subset membership.
- Do not guess when selector resolution is ambiguous.
- Keep direct-mode output compact and deterministic.

## Output

Execute the company-list expansion directly instead of replying with an informal plan.
