---
name: sec-filings-audit-download
description: Use when downloading a new public company's SEC EDGAR filings for a date window, or auditing an existing archive for complete accessions and missing files.
---

# SEC Filings Audit & Download

用同一流程处理两类任务：为新标的完整归档一段时间内的 SEC 申报，或检查已有归档并增量补齐。以 SEC submissions 数据中的 accession 为完整性标准，不要根据文件夹数量、文件名或搜索结果推断已完整。

## 两种模式

| 场景 | 命令行为 |
| --- | --- |
| 新标的完整归档 | 不加 `--audit-only`。空归档中所有官方 accession 都是缺口，脚本会下载整个日期窗口内的申报并生成 manifest。 |
| 已有归档检查 | 加 `--audit-only`，只输出官方 accession 与本地文件的缺口，不写入下载结果。 |
| 已有归档增量补齐 | 不加 `--audit-only`。脚本先核对，再只下载缺失或不完整的 accession。 |

默认窗口是运行日往前最近七个自然年，结束日为运行日；传入 `--start-date` 和 `--end-date` 可改为任何明确区间。

## 工作流

1. 从 `data.sec.gov/submissions` 拉取当前及历史 submissions 文件，合并日期范围内的官方 accession。
2. 对已有文件，逐项检查 manifest、归档目录、完整 submission 文本和所选范围要求的文件。
3. 纯检查使用 `--audit-only`；下载模式只处理审计确认的缺口。
4. 保存 manifest、审计结果和来源索引增量；下载失败、缺附件或路径失效时保留问题记录。

## 新标的完整归档

```bash
python3 scripts/sec_filings_audit_download.py \
  SYMBOL \
  --project-root /path/to/research-project \
  --document-scope submission \
  --user-agent "$SEC_USER_AGENT"
```

上例使用默认最近七年窗口并直接下载。`submission`（默认）保存 SEC 的完整原始 submission 文本；需要独立主文件时选 `filing`，需要 HTML/XML/TXT/PDF 文件时选 `html`，需要归档目录所有文件时选 `full`。

## 仅检查或增量补齐

```bash
python3 scripts/sec_filings_audit_download.py \
  SYMBOL \
  --project-root /path/to/research-project \
  --audit-only \
  --user-agent "$SEC_USER_AGENT"
```

确认缺口后，移除 `--audit-only` 以增量下载。必要时提供 `--cik`，避免名称或代码映射歧义。

`--user-agent` 必须由使用者提供，并应符合 SEC 对可识别联系信息和合理请求频率的要求。脚本不会保存该值。

## 完成标准

在指定日期范围和选择的文件范围内，只有同时满足以下条件才可称为完整：官方 accession 无缺口、每条 manifest 路径可解析、归档 submission 完整，且所选范围要求的主文件存在。下载完成不代表披露内容已经过事实验证。
