# Evidence Card Schema

## Required Folder

Create one folder per ticker:

`archive/evidence_cards/`

Required files:

- `<TICKER>001.md`, `<TICKER>002.md`, ...
- `index.csv`
- `datapoints.csv`
- `README.md`
- `open_items.md`

## Markdown Card Fields

Each source gets one Markdown file with these sections:

```markdown
# <TICKER>001 - <source title>

## 基本信息

- Evidence ID: <TICKER>001
- 日期: YYYY-MM-DD
- 标题: ...
- 来源: SEC EDGAR / HKEX / Company IR / Partner official site / ...
- 文件类型: 20-F / 6-K / 424B5 / investor presentation / earnings release / transcript / press release / blog / video / ...
- 官方链接: https://...
- 本地路径: archive/...
- 访问日期: YYYY-MM-DD

## 内容摘要

300-800字。只摘要事实，不写主观评价，不下投资结论。

## 重要数字

| 指标 | 数值 | 单位 | 语境 | 证据标签 |
|---|---:|---|---|---|

## 事件标签

`Management`, `Financing`, ...

## 可以支持哪些投资结论

- GPU规模扩大
- 获得Anchor Customer
```

## Numeric Extraction Scope

Extract all disclosed facts involving:

- GPU, GPU model, GPU count
- MW, power, data center sites, regions, colocation, owned data centers
- CapEx, purchases of PPE/intangibles, cash, debt, financing proceeds
- Revenue, ARR, EBITDA, adjusted EBITDA, net income/loss
- RPO, backlog, deferred revenue, customer prepayments
- Customers, contract value, contract term, delivery conditions
- Acquisition consideration, earnouts, equity changes, warrant/share counts

If a source does not disclose a requested number, write `待核实` or `missing_required_source`; do not infer.

## Event Tags

Allowed tags include:

- `Management`
- `Financing`
- `Acquisition`
- `Data Center`
- `GPU`
- `Customer`
- `Microsoft`
- `NVIDIA`
- `Meta`
- `AI Cloud`
- `NeoCloud`
- `AIDC`
- `Revenue`
- `RPO`
- `Guidance`

Add a new tag only when the source requires it.

## CSV Requirements

Use UTF-8 with BOM for CSV files likely to be opened in Excel.

`index.csv` columns:

`evidence_id,date,title,source,file_type,official_url,local_path,tags,supports,accessed_at`

`datapoints.csv` columns:

`evidence_id,company,metric,value,unit,period_or_context,source_title,source_type,official_url,local_path,evidence_label,accessed_at`

## QA Checklist

Before finishing:

- Card count equals index row count.
- Evidence IDs are unique and use ticker prefix.
- No old generic `EV###` IDs remain.
- Every card has all required sections.
- Every summary is 300-800 Chinese characters unless the source is genuinely too thin; if so, explain in `open_items.md`.
- Every local path exists.
- Every number has a source and evidence label.
- Conflicting official numbers are recorded in `qa/discrepancy_log.md`.
- Missing partner announcements, transcripts, videos, and undisclosed deal amounts are recorded in `open_items.md` and project `qa/open_questions.md`.
