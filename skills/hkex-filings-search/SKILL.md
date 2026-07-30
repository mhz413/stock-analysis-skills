---
name: hkex-filings-search
description: Use when collecting, verifying, downloading, archiving, or citing HKEXnews filings for Hong Kong listed issuers, including announcements, circulars, annual reports, interim reports, and official disclosure searches.
---

# HKEX Filings Search

以 HKEXnews 为港股正式披露的首要来源。先解析交易所内部 `stockId`，再按精确日期区间检索并保存原始搜索结果。

## 工作流

1. 调用 `prefix.do`，按股票代码选择唯一的精确匹配并取得 `stockId`。
2. 使用 `stockId`（而不是代码）调用 `titleSearchServlet.do`，并使用 `fromDate`、`toDate` 与足够的 `rowRange`。
3. 保存原始 JSON 响应，再根据研究问题筛选所需 PDF。
4. 为每份保留文件记录官方 URL、相对路径、访问日期和来源等级；文本提取仅作为检索辅助，PDF 才是原件。
5. 区分公告日、通函日、完成日、报告期末和并表期间。来源冲突必须保留并记录。

## 运行

```bash
python3 scripts/hkex_title_search.py HK_CODE \
  --from-date YYYYMMDD \
  --to-date YYYYMMDD \
  --out-json /path/to/raw-search.json \
  --print-table
```

需要下载时，加入 `--download-dir /path/to/official-filings`；需要文本索引时，再加入 `--extract-text`。用 `--download-filter` 仅下载与问题相关的标题。

## 常见错误

- 把 `result` 当作已解析 JSON：先解析顶层响应，再解析其嵌套结果。
- 用 `from`/`to` 替代 `fromDate`/`toDate`：搜索会不完整或为空。
- 将框架协议、意向或授信额度写成已实现收入或现金：只使用文件明确披露的状态。
- 因另一个官方来源冲突而删除其中一个数字：两个数字都保留，并注明范围和时间差异。
