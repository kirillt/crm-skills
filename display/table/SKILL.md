---
name: display-table
description: Internal adapter for routing Markdown table output to chat or an external viewer. Use whenever a skill or task has a Markdown table to present, whether the table is supplied as text or as a file.
---

# Display Table

This is the shared presentation adapter for Markdown table output.

It accepts a table as Markdown text or as a file path, applies the output-routing rules, and displays the table. It must never edit an input file.

## Inputs

Accepted input forms:

- Markdown table text supplied in the current reasoning/chat context.
- A Markdown file path containing the table.

The input may contain one table or a small bundle of related Markdown tables. Treat the bundle as one display unit.

## Output Routing

1. If the user explicitly states an output method, use that method.
   - Chat examples: "show in chat", "paste it here".
   - File/viewer examples: "open it", "use external viewer", "save to file".
2. Otherwise, count table body rows across the input display unit.
   - Count Markdown table body rows, excluding header and separator rows.
   - If there are multiple tables, sum their body rows.
3. If the total is less than 10 rows, output in chat.
4. If the total is 10 or more rows, output to a file and invoke the external viewer.

Use the same external viewer already used by repository display flows: Marked 2 via `open -a "Marked 2" <file>`.

If the external-open step is required and fails, treat it as blocking and retry with elevated permissions when needed.

## Input / Output Combinations

Input file, output file:

- If no transformation is needed, invoke the viewer on the input file directly.
- If transformation is needed, create a new Markdown file under `output/`; do not edit the input file.

Input file, output chat:

- Read the input file and output the table in chat.
- If transformation is needed, apply it in memory; do not create a new file.

Input chat/text, output file:

- Write the table to a new Markdown file under `output/` and invoke the viewer.
- If transformation is needed, apply it in memory before writing.

Input chat/text, output chat:

- Output the table in chat.
- If transformation is needed, apply it in memory before outputting.

## File Output

- Write exactly one Markdown file under `output/` when creating a new file.
- Use a descriptive filename such as `output/display-table-<slug>-<YYYYMMDD-HHMMSS>.md`.
- Do not create sidecar files for the same table display.
- Do not write continuation-critical state to `output/`.

## Caller Guidance

- Skills with table output should pass their final Markdown table to `$display-table` instead of deciding chat-vs-file locally.
- If a Python script already wrote the table to a file, pass that file path directly to this adapter.
- If a Python script only prints Markdown to stdout and a transformation is needed, pass the Markdown text to this adapter after the transformation is applied in memory.
- When the table is part of an approval gate, the adapter still owns presentation; the caller owns the approval semantics after the table is displayed.

## Non-Negotiables

- Never edit the input file.
- Never silently complete without displaying the table either in chat or in the external viewer.
- Do not mutate canonical data.
