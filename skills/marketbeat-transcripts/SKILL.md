---
name: marketbeat-transcripts
description: Use when searching MarketBeat or extracting a MarketBeat / Quartr earnings-call transcript page to JSON for public-company research.
---

# MarketBeat Transcripts

将 MarketBeat / Quartr 作为第三方纪要备选来源。它可补足其他来源缺失的季度，但不能替代公司或监管正式披露。

## 运行

按证券代码搜索：

```bash
python3 scripts/extract_marketbeat_transcript.py \
  --symbol SYMBOL \
  --quarter 2024Q1 \
  --output-dir /path/to/earnings-transcripts
```

已知页面时使用 `--url`；已保存页面时使用 `--html-file`。若搜索路径不明确，可使用 `--exchange` 指定交易所路径段。

## 归档纪律

- 输出使用 `SYMBOL_YYYYQn.json`；记录页面 URL 与提取时间。
- 先查看输出中的标题、季度和发言人数量，确认页面解析没有误匹配。
- 网站访问受限时，记录失败原因；不要把搜索失败解释为不存在纪要。
- 使用纪要中的数字前，仍需与正式申报、业绩新闻稿或公司 IR 材料交叉核对。
