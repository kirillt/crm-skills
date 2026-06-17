---
name: export
description: Create shareable lead handover archives for BD/Sales representatives from canonical people and company entities. Use when the user invokes `$export`, asks to export leads/contacts/companies/people, package CRM entity JSON for a BD or sales teammate, create a ZIP handoff, or transform canonical CRM data into a shareable artifact without creating new entities.
---

# Export

## Goal

Use this skill to hand over leads to BD/Sales representatives in a compact, readable archive built from existing canonical CRM data.

The export should help the recipient understand:
- who the relevant person is
- which company they are tied to
- what relationship or communication history exists
- why the company is technically/business relevant
- which prior audit links can be used as proof points

Exports are copies, not canonical storage.

## Storage

Use the top-level `export/` folder for all export artifacts.

Default layout:

```text
export/<slug>-<YYYY-MM-DD>/
  payload/
    manifest.md
    handoff-prompt.txt
    leads/<company-id>/
      company.json
      cache.json
      <person-id>.json
      considered/
        <considered-entity-id>.json
        <considered-entity-id>.md
  <slug>-<YYYY-MM-DD>.zip
```

When updating an existing export, update its unpacked `payload/` and rebuild the ZIP from that payload.

Each lead folder is keyed by canonical company ID. Do not create extra summary JSON files by default; the exported company, person, cache, considered-entity, manifest, and handoff prompt are the dataset. Add an extra report file only when the user explicitly asks for one.

## Entity Resolution

1. Resolve requested people/companies using canonical IDs, names, aliases, and repo typo-tolerant resolution rules.
2. Copy only entities needed for the handover.
3. For a person-company lead, include the exported person and their linked company.
4. Include `cache/companies/<company-id>.json` as `cache.json` whenever it exists.
5. If an entity is referenced in canonical comms or in the requested handover but is not canonical, search active/recent `$consider-*` scratch state for the matching staged entity. Include the staged files under `considered/` and label them clearly in `manifest.md` and `handoff-prompt.txt`.
6. Do not create new canonical entities during export. If a needed entity has no canonical or considered record, route first-touch intake through `$consider`, `$consider-people`, or `$consider-companies` before exporting or report the blocker.

## Export Transforms

Apply transforms to exported copies only unless the user explicitly asks to correct canonical data.

### Staff

For person-company lead handovers, filter exported company `"staff"` to only exported people for that company.

Convert role codes into human-readable titles in exported JSON.

Example:

```json
{"id":"{alice}","role":"CTO"}
```

becomes:

```json
{"id":"{alice}","role":"Chief technology officer"}
```

If an exported person-side `"companies"` item has `"role":["COF","CEO"]`, export it as `"role":["Co-founder","Chief executive officer"]`.

Role title mapping:
- `CEO`: Chief executive officer
- `CBDO`: Chief business development officer
- `CTO`: Chief technology officer
- `COO`: Chief operating officer
- `COF`: Co-founder
- `FOU`: Founder
- `BD`: Business development
- `ENG`: Engineer
- `PENG`: Protocol engineer
- `RES`: Researcher
- `CRES`: Cryptography researcher
- `SEC`: Security
- `OPS`: Operations
- `GM`: General manager
- `HEAD`: Head of function
- `LEAD`: Technical lead
- `DIR`: Director
- `PROD`: Product/program manager
- `COMM`: Community/communications
- `GTM`: Growth/marketing
- `OWNER`: Owner/proprietor
- `PHOTO`: Photographer
- `EIR`: Entrepreneur in residence
- `DREL`: Developer relations
- `INV`: Investment/portfolio management

For unknown role codes, expand conservatively if obvious; otherwise preserve the code and mention it in chat.

### Communication History

For exported company `"comms.events"`, keep only:
- direct comms involving exported people
- group-chat events where at least one exported person is explicitly involved
- direct comms involving exported considered people when those considered records are included under `considered/`

Exclude direct events involving only non-exported people.

Do not assume hidden group membership. If local source cache exists for an ambiguous group event, verify exported-person participation against `cache/telegram/` before keeping it.

Person `"comms.events"` may remain complete for that exported person unless the user asks for a narrower slice.

### Audits

In exported company JSON, replace canonical company `"audits"` counts with links to our audit work, including direct Taran.Space work and outsourced/under-another-brand work such as Oak.

Export schema:

```json
"audits": {
  "YYYY-MM-DD": "https://..."
}
```

Use project dates from `projects/*.json` when available. Use the first day of each audit period as the key. Values must be public report links from the matching project `"reports"` list. If no qualifying public report link exists, use `{}`.

Do not mutate canonical company `"audits"` for this export transform.

### Cache

Copy `cache/companies/<company-id>.json` as `cache.json` for every exported company when available. Do not transform cache field names or values. The cache is part of the handover because it carries current summary, temperature, chances, latest comms, and contactability.

### Considered Entities

Considered entities are not canonical, but they are often exactly where handover-critical links live before final persistence. When a relevant person/company is only staged:
- copy the staged JSON/Markdown evidence into `considered/`
- preserve the original staged wording and source links
- state in `manifest.md` that the record is considered/staged, not canonical
- include it in `handoff-prompt.txt` if it affects the recipient's next action

Do not convert considered entities into invented export-only canonical-like objects. Either copy the staged artifact as-is, or promote the entity through the appropriate `$consider-*` workflow first when the user approves persistence.

## Handoff Prompt

Include `handoff-prompt.txt` for BD/Sales AI handover unless the user says not to.

Default constraints:
- under 1000 characters
- explain the JSON scheme and how useful context can be interpreted
- do not include outreach instructions unless explicitly requested
- process every exported company, person, cache, and considered file; do not base the prompt on only the canonical company/person files
- mention every exported lead and every non-canonical considered route that materially affects next steps

## ZIP Hygiene

The ZIP should contain only intentional handover files: manifest, optional handoff prompt, and lead folders. Lead folders may contain `company.json`, `cache.json`, exported `<person-id>.json` files, and `considered/` staged artifacts. Keep transient reports, scratch files outside `considered/`, prior ZIPs, and `.DS_Store` out of the archive.

## Validation

Before finishing:
- Confirm exported JSON parses with `jq`.
- Confirm exported company staff lists contain only exported people for person-company lead exports.
- Confirm role codes in exported role fields were converted to human-readable titles.
- Confirm kept company comms mention exported person IDs or are source-verified group events.
- Confirm exported `"audits"` maps dates to URL strings, not numeric counts.
- Confirm `cache.json` is present for every company with an existing company cache, or record its absence in `manifest.md`.
- Confirm every relevant non-canonical entity mentioned in exported comms or requested handover context is either included under `considered/`, promoted canonically through the appropriate `$consider-*` workflow, or listed as a blocker in `manifest.md`.
- Confirm `handoff-prompt.txt` was generated from the complete exported payload, including cache and considered files.
- Rebuild the ZIP and list its contents.

If canonical entities were changed in the same turn, run matching validators and write logs under `logs/validators.log/`.

## Output

In chat, return:
- the ZIP path/link
- a concise summary of material transforms
- any unresolved role codes or source gaps

Do not paste large reports unless the user asks for them.
