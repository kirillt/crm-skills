---
name: outreach-adjust
description: Refine the stored outreach style based on user-provided sent messages and prior drafts. Use when the user explicitly invokes `$outreach-adjust`, asks to tune outreach style, or when `$outreach-draft` invokes it after sent-message tracking. Compare user wording against prior drafts, summarize the strongest improvements, and update `state/outreach/style.json` while keeping the style compact and distinctive.
---

# Outreach Adjust

## Overview

Use this skill to modify the stored outreach voice.

This is the only mutation surface in the `outreach` family.
It reads the current state from `state/outreach/style.json`, compares real user messages against prior drafts when available, and writes the improved distilled rules/examples back into that JSON file.

## Trigger Conditions

Use this skill when:
- the user explicitly invokes `$outreach-adjust`
- the user asks to refine, tune, learn, or update the outreach style
- `$outreach-draft` has just tracked one or more actually sent outreach messages

If the user reports sent messages directly and they have not yet been tracked canonically, route through `$outreach-draft` first. This skill must not replace or bypass communication persistence.

## Inputs

- If the input is empty:
  - first inspect the latest user turn for any actual outreach message text the user just provided or quoted
  - if such a message exists, treat it as in scope even without an explicit argument
  - then scan the current session for prior `$outreach-draft` invocations and extract the drafts that were produced
  - if there are no usable draft examples in the current session, say so briefly and still compact or prune the stored style JSON
- If the input is non-empty:
  - treat the provided messages as the user-preferred final wording
  - find the corresponding prior `$outreach-draft` output for each message
  - match primarily by person name, and secondarily by company, domain, protocol, role, or topic anchors
  - prefer the newest actual user-provided message in the current turn when there is any ambiguity

## Procedure

1. Read the current stored rules/examples from `state/outreach/style.json`.
2. Collect the comparison set.
   - Start with the newest actual user-provided outreach message in the current turn when one exists.
   - Resolve each user-provided sent message to its closest earlier `$outreach-draft` output when possible.
   - If more than one draft could match, prefer the most recent same-session `$outreach-draft` output.
   - Do not ignore the latest actual user message just because an older message/draft pair is easier to match.
   - If the latest user message cannot be matched confidently, say that explicitly and still analyze it as fresh style evidence.
3. Compare each pair briefly.
   - Extract the differences between the actually sent user message and the matched `$outreach-draft` output.
   - Extract the strongest positive differences in the user version.
   - Note any tradeoffs or risks introduced by the user version.
   - Keep the analysis short and specific.
4. Update `state/outreach/style.json`.
   - Revise `core_style_summary` when the new signal changes the center of gravity.
   - Add or adjust `specific_rules` only when the new signal teaches a durable pattern.
   - Consider whether the new example is distinct enough to keep after the rules are updated.
5. Apply pruning deliberately.
   - Keep the style compact:
     - 1 core summary
     - up to 10 specific rules or exceptions
     - at most 20 examples
   - Prefer the most distinct examples across different outreach situations, not near-duplicates with the same structure.
   - When adding a new example:
     - first adjust the rules if needed
     - then decide whether the new example is useful under the updated rules
     - if the example set is full, remove the single least useful example and replace it only if the new example is more distinct or more response-likely
   - If the new example is weaker than the current set, do not add it.
6. Return the analysis.
   - Output brief differences plus pros and cons.
   - State whether the style JSON was updated and whether any example was pruned or rejected.

## Non-negotiable Rules

- This skill is the only place allowed to mutate `state/outreach/style.json`.
- The latest actual user-provided outreach message in the current turn must be considered first whenever one is present.
- Every example written into the style JSON must be a real user-provided message.
- Never invent, paraphrase, or synthesize examples for the style JSON.
- Compare actually sent user messages against matched `$outreach-draft` outputs whenever such drafts exist, and extract differences from that comparison.
- Choose examples by expected chance of response and distinctiveness, not by recency alone.
- Reject changes that make the message longer, fuzzier, more salesy, less truthful, or more generic unless there is a clear countervailing benefit.
- Do not store private operational noise, dates, or long explanations inside the style JSON.

## Output

When you use this skill, return the brief comparison analysis and update `state/outreach/style.json` in the same turn instead of replying with an informal plan.
