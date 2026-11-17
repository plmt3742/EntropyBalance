# data/golden

抽取评测的标注集与口径。所有准确率表述只能引用这里的版本。

## 计划内容

| 文件 | 内容 |
|---|---|
| `annotation-guide.md` | 标注规范：字段定义、边界案例、分歧裁决规则 |
| `v0/*.jsonl` | 标注数据：记录 + 期望断言 + 证据偏移 |
| `splits.json` | 开发/测试划分（按记录，不按断言） |
| `eval-YYYY-MM-DD.json` | 某次评测的完整结果（模型、提示词版本、指标） |

## 标注格式（草案）

```json
{
  "record_id": "R001",
  "assertions": [
    {
      "type": "task",
      "subject": "P01",
      "predicate": "owns",
      "object": "整理报名表",
      "due": "2026-09-20",
      "evidence": {"start": 42, "end": 57, "quote": "报名表我来整理，周五前给"},
      "confidence": "certain"
    }
  ]
}
```

## 规则

- 双人独立标注，分歧记录理由；不追求"统一成一个人"。
- 证据偏移以字符计，必须能在原文中精确切出。
- 标注集脱敏后再入库；`annotation-guide.md` 与数据同版本。
- 不允许为了让指标好看而删样本；确需剔除时记录原因与数量。
