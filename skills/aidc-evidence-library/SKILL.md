---
name: aidc-evidence-library
description: Use when building, updating, auditing, or compressing a traceable evidence library for a listed company in AI infrastructure, cloud computing, GPU services, or data-center research.
---

# AIDC Evidence Library

建立分析叙事之前，先建立可追溯底稿：

`Sources -> Evidence Cards -> Datapoints -> Reviewed Numbers -> Events`

## 工作流

1. 先读项目规则，盘点已有原件和来源索引，避免重复下载。
2. 按监管机构或交易所、正式披露、公司 IR、合作方披露、可靠媒体的顺序搜索。
3. 每个公开来源建立一张 Evidence Card，并记录原始链接、访问日期、本地相对路径、证据类别与不确定性。
4. 为关键数字记录单位、期间、范围、计算公式和来源；来源冲突写入 `qa/discrepancy_log.md`。
5. 只有在证据库足以支撑时才压缩为经济事件；不要将公告日期本身当作事件。

## 证据纪律

- 不将公司陈述等同于独立验证。
- 不将意向、框架协议或额度等同于合同收入、现金收款或已提款债务。
- 不将算力指标等同于经核实的硬件清单、容量、利用率或所有权。
- 不将合同对价、会计公允价值和实际现金支付混为一谈。
- 无法确认时使用 `待核实`；不要以推断替代来源。

阅读 [Evidence Card schema](references/evidence_card_schema.md) 后再写卡片；对关键数字或交易条款，阅读 [review schema](references/review_schema.md)；建立事件层前阅读 [event schema](references/event_library_schema.md)。

## 建议目录

```text
archive/
  official/
  ir/
  third_party/
  evidence_cards/
```

运行校验器：

```bash
python3 scripts/validate_library.py /path/to/evidence_cards
```

校验通过并不代表商业事实已得到独立确认；它只确认结构、引用和映射的完整性。
