---
name: display
description: Route presentation-only entity display requests into the correct display skill. Use when the user invokes $display, asks to display companies or people, or uses legacy display task names such as \companies\display and the target kind is mixed or unclear.
---

# Display

This is a thin router for presentation-only views. It must not create or update canonical entities.

## Dispatch

- Company targets, company selectors, rubric expressions, or legacy `\companies\display` invocations: use `$display-companies`.
- Person targets, person names/IDs/LinkedIn URLs, or requests such as "give me details on these people as a table": use `$display-people`.
- Raw Markdown table text or a Markdown table file that only needs presentation routing: use `$display-table`.
- Mixed company and person targets: run the relevant worker skills and assemble one final presentation, unless the output would be clearer as separate sections.
- Unclear target kind: ask one concise clarifying question before doing work.

## Presentation Contract

- A display task is not complete until the result is actually displayed.
- All Markdown table output must be routed through `$display-table`.
- Do not mutate `companies/*.json`, `people/*.json`, `projects/*.json`, `cache/companies/*.json`, or `aliases.json`.
