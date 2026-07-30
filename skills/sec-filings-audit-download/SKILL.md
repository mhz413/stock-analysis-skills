---
name: sec-filings-audit-download
description: Use when checking SEC EDGAR filing completeness, reconciling official accessions, incrementally archiving missing submissions, or validating a public-company filing manifest.
---

# SEC Filings Audit & Download

以 SEC submissions 数据中的 accession 为完整性标准，再下载本地缺口。不要根据文件夹数量、文件名或搜索结果推断已完整。

## 工作流

1. 从项目根目录确认归档范围、起止日期和已有 manifest。
2. 从 `data.sec.gov/submissions` 拉取当前及历史 submissions 文件，合并范围内 accession。
3. 将官方 accession 与本地 manifest、归档目录、完整 submission 文本及所需主文件逐项核对。
4. 先运行 `--audit-only`；只在缺口明确后下载缺失项。
5. 每次运行都保存可复查的 manifest；出现下载失败、缺附件或路径失效时保留问题记录。

## 运行

```bash
python3 scripts/sec_filings_audit_download.py \
  SYMBOL \
  --project-root /path/to/research-project \
  --start-date 2024-01-01 \
  --end-date 2026-12-31 \
  --audit-only \
  --user-agent "$SEC_USER_AGENT"
```

确认缺口后，移除 `--audit-only` 重新运行。必要时提供 `--cik`，避免名称或代码映射歧义。

`--user-agent` 必须由使用者提供，并应符合 SEC 对可识别联系信息和合理请求频率的要求。脚本不会保存该值。

## 完成标准

在指定日期范围和选择的文件范围内，只有同时满足以下条件才可称为完整：官方 accession 无缺口、每条 manifest 路径可解析、归档 submission 完整，且所选范围要求的主文件存在。下载完成不代表披露内容已经过事实验证。
