# Stock Analysis Skills

可复用的公开公司研究技能组合，覆盖证据库、SEC EDGAR、HKEXnews 和业绩电话会纪要归档。每个技能都以官方来源、原始文件留存、可追溯索引和不确定事项记录为核心。

## 包含的技能

| 技能 | 用途 |
| --- | --- |
| `aidc-evidence-library` | 建立并审计 AI 基础设施与数据中心研究的证据、数据点和事件库。 |
| `sec-filings-audit-download` | 对照 SEC 官方 accession 清单检查完整性，只增量下载缺失申报。 |
| `hkex-filings-search` | 搜索、保存和引用 HKEXnews 正式披露。 |
| `alpha-vantage-transcripts` | 使用使用者自备的 Alpha Vantage key 下载业绩电话会纪要。 |
| `marketbeat-transcripts` | 提取 MarketBeat / Quartr 电话会纪要页面为 JSON。 |

## 使用方式

将所需的技能目录复制到你的 Codex 技能目录，或按你的运行环境所支持的技能安装方式导入。先阅读每个目录的 `SKILL.md`，再执行其中的脚本。

此仓库不含研究资料、下载结果、公司实例、股票代码、绝对路径、个人资料或凭证。需要 API 的脚本只接受你在运行时自行提供的 key；不会存储 key 或创建配置文件。

## 研究纪律

- 将用户提供的事实和管理层陈述视为待核实假设。
- 对关键数字保留原始来源、链接、期间、单位和证据状态。
- 将监管或交易所正式文件与第三方材料区分开来。
- 将未解决的来源冲突记录为待核实事项，而不是静默消除。

## 许可

本仓库以 [MIT License](LICENSE) 发布。
