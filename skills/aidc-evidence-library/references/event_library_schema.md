# Event Library Schema

## Required files

- `event_library.md`
- `event_library.csv`
- `event_to_evidence_map.csv`
- `event_open_items.md`
- `event_open_items.csv`

## Event fields

Use:

`event_id,event_date_or_range,event_name,event_type,evidence_ids,key_datapoints,what_changed,business_model_impact,valuation_relevance,disputed_or_unresolved,unresolved_reason,confidence,can_be_used_in_report,suggested_report_wording`

Use stable IDs such as `<TICKER>_EVT001`. Dates describe the event window, not a narrative timeline.

## Mapping fields

Use:

`event_id,event_name,evidence_id,evidence_role,evidence_date,source_type,source_title,official_url,local_path,key_fact_for_event`

Each event must map to at least one existing Evidence ID. Use `evidence_role` to distinguish proposal, terms, approval, completion, financial confirmation, partner confirmation, and contradiction.

## Selection rule

Create an event only when evidence shows a meaningful change or establishes a decision-relevant baseline. Group procedural filings into the same event unless they independently change completion risk, ownership, economics, or accounting scope.

Valid event domains include business transformation, acquisition/disposal, consolidation, customer/contract validation, operating assets, financing, capital structure, control/shareholding, management, and reported financial contribution.

Administrative filings may be retained as Low relevance events when needed for full evidence coverage, but must not crowd out business-changing events.

## Ratings

### Valuation Relevance

- `High`: changes earnings scope, core business model, control, major assets, material financing, or verified customer/revenue economics.
- `Medium`: supports execution capacity or removes a meaningful condition, but does not independently establish earnings change.
- `Low`: governance, administrative, or audit-trail relevance with limited direct economic effect.

### Confidence

- `High`: authoritative source directly proves the stated event mechanics.
- `Medium`: issuer claim is official but underlying commercial fact lacks counterparty/asset verification, or evidence is incomplete.
- `Low`: management outlook, thin website/interview evidence, or material ambiguity.

Confidence applies to the event wording, not every downstream implication.

## Unresolved discipline

Set `disputed_or_unresolved=Yes` whenever material scope, counterparties, accounting, completion, cash receipt, asset ownership, capacity, or source conflict remains. Copy all such events into `event_open_items.csv`; the Markdown file should explain what evidence would resolve each item.

`can_be_used_in_report` should be `Yes`, `With Caution`, or `No`. Qualified wording must retain issuer attribution and the unresolved boundary.
