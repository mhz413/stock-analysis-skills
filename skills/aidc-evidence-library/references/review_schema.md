# Critical Review Schema

## Key-number review

Create one row per material number with these columns:

`item,number_original,source_file,evidence_id,page_or_location,official_quote,unit,period,classification,direct_use,downgrade_needed,differences,unresolved`

The Markdown version should preserve the same fields in a readable table or one section per number.

Classify each number as one of: actual, intention/framework, forecast/guidance, target, estimate, derived calculation, or management statement. Add audit/review status where known.

### Required checks

- Quote the shortest official text that preserves meaning; add page or announcement section.
- Separate group, segment, subsidiary, acquisition target, and post-consolidation scopes.
- Separate full-year target-company results from the listed company's consolidation period.
- Separate gross value, net value, currency, and translated currency.
- State whether the figure is directly report-usable, usable only with qualified wording, or not usable.
- Preserve every unresolved item; never fill a missing fact by inference.

## Partner-side review

Create one row per named partner with:

`partner,partner_side_evidence,evidence_id,suggested_search_path,affected_conclusions`

`partner_side_evidence` is Yes only when the current library contains the counterparty's own website, filing, press release, investor material, or regulator-filed document supporting the relationship. Issuer disclosure alone remains `No` or `Missing`, even when filed with an exchange.

Search partner IR/newsrooms, regulatory filings, product/customer case studies, official blogs, and event presentations. Record absence; do not manufacture a negative conclusion from silence.

## CSV

Write human-facing CSV as UTF-8 with BOM. Keep one canonical row per item and stable Evidence IDs.
