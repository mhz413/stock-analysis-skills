---
name: alpha-vantage-transcripts
description: Use when downloading and archiving Alpha Vantage earnings-call transcript JSON for public-company research, including selected quarters or complete years.
---

# Alpha Vantage Transcripts

将 Alpha Vantage 作为第三方电话会纪要来源，而不是监管或公司正式披露。保留原始 JSON，并在使用其中的数字前与正式披露交叉核对。

## 运行

使用者须在运行时提供自己的 key，方式二选一：传入 `--api-key`，或设置 `ALPHA_VANTAGE_API_KEY` 环境变量。脚本不提供默认 key，也不写入配置文件。

```bash
python3 scripts/fetch_alpha_vantage_transcripts.py \
  --symbol SYMBOL \
  --quarters 2024Q1 2024Q2 \
  --output-dir /path/to/earnings-transcripts
```

需要全年时使用 `--years YEAR YEAR`。单一季度可使用 `--quarter` 和可选的 `--output`。

## 归档纪律

- 使用一致的 `SYMBOL_YYYYQn.json` 文件名。
- API 返回空纪要时，不要将空响应包装成证据；记录该季度不可用。
- 将来源、URL、访问日期和本地相对路径写入项目来源索引。
- 从控制台输出中保留 key 脱敏；共享日志前仍要检查是否有其他敏感内容。
