# JSON Schemas

所有数据在内存中流转，仅产出一个文件：`{skill_name}.check.json`。

---

## check.json — 唯一产出文件

包含测试集、触发评测、环境扫描、TRACE 五维评测、优化记录的完整数据。

```json
{
  "skill_name": "my-skill",
  "timestamp": "2026-03-07T12:00:00+00:00",
  "overall_score": 0.85,
  "trace": {
    "trust": {"score": 0.9, "label": "可信任度", "verdict": "优秀", "issues": []},
    "reliability": {"score": 0.85, "label": "可靠性", "verdict": "良好", "issues": [...]},
    "adaptability": {"score": 0.75, "label": "适用性", "verdict": "需修复", "issues": [...]},
    "convention": {"score": 1.0, "label": "规范性", "verdict": "优秀", "issues": []},
    "effectiveness": {"score": 0.9, "label": "有效性", "verdict": "优秀", "issues": []},
    "overall": 0.88,
    "conclusion": "可用，但需修复",
    "conclusion_detail": "部分维度需修复后即可正常使用，修复成本可控"
  },
  "evals": [
    {"query": "帮我检查这个 skill", "should_trigger": true},
    {"query": "帮我写一个新 skill", "should_trigger": false}
  ],
  "dimensions": {
    "trigger": {
      "status": "checked",
      "score": 0.9,
      "description_used": "Use this skill when...",
      "results": [
        {"query": "...", "should_trigger": true, "triggered": true, "pass": true}
      ],
      "summary": {"total": 20, "passed": 18, "failed": 2, "pass_rate": 0.9}
    },
    "environment": {
      "status": "checked",
      "score": 0.875,
      "dependencies": [
        {
          "category": "tool",
          "name": "bash",
          "description": "what the skill needs",
          "evidence": "quote from SKILL.md",
          "compatibility": "compatible",
          "reason": "why"
        },
        {
          "category": "capability",
          "name": "user_choices",
          "description": "Presents options to user",
          "evidence": "Step 3: Present 3-5 options",
          "compatibility": "adaptable",
          "reason": "Has structured clarification",
          "adaptation": {
            "target_capability": "clarification tool",
            "strategy": "replace",
            "description": "Use clarification tool instead of text",
            "changes": ["Replace text-based option listing with clarification tool"]
          }
        }
      ],
      "summary": {
        "total": 8, "compatible": 5, "adaptable": 1, "incompatible": 1, "unknown": 1,
        "blocking_issues": ["anthropic_sdk"],
        "adaptations_available": ["user_choices"],
        "fitness_score": 0.75
      }
    }
  },
  "optimization": {
    "iterations": [
      {"iteration": 1, "description": "...", "train_passed": 10, "train_total": 12}
    ],
    "best": {"description": "...", "test_score": 0.95}
  }
}
```

### 顶层字段

| Field | Type | Description |
|-------|------|-------------|
| `skill_name` | string | Skill 名称 |
| `timestamp` | string | ISO 8601 UTC |
| `overall_score` | float | trigger + environment 两个维度的均分 (0.0–1.0) |
| `trace` | object | **TRACE 五维评测结果**（含结论） |
| `evals` | object[] | 测试集（query + should_trigger） |
| `dimensions.trigger` | object | 触发评测维度 |
| `dimensions.environment` | object | 环境扫描维度 |
| `optimization` | object | 优化迭代记录（可选，仅优化时产出） |

### trace 对象（TRACE 五维评测）

| Field | Type | Description |
|-------|------|-------------|
| `trust` | object | T - 可信任度：{score, label, verdict, issues} |
| `reliability` | object | R - 可靠性：{score, label, verdict, issues} |
| `adaptability` | object | A - 适用性：{score, label, verdict, issues} |
| `convention` | object | C - 规范性：{score, label, verdict, issues} |
| `effectiveness` | object | E - 有效性：{score, label, verdict, issues} |
| `overall` | float | 五维均分 (0.0–1.0) |
| `conclusion` | string | 最终结论：`"可直接使用"` / `"可用，但需修复"` / `"不可用，需修复"` |
| `conclusion_detail` | string | 结论的详细说明 |

每个维度对象结构：
```json
{
  "score": 0.85,
  "label": "可靠性",
  "verdict": "良好",
  "issues": ["有 1 项依赖状态未知，存在运行时风险"]
}
```

判等阈值：`>= 0.9` 优秀 / `>= 0.8` 良好 / `>= 0.6` 需修复 / `< 0.6` 不合格

整体结论：
- 全部 `>= 0.8` → `"可直接使用"`
- 任一 `< 0.6` → `"不可用，需修复"`
- 其余 → `"可用，但需修复"`

### trigger 维度

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"checked"` or `"skipped"` |
| `score` | float | pass_rate |
| `description_used` | string | 被测试的 description |
| `results[]` | object[] | 每条 query 的 triggered/pass 结果 |
| `summary` | object | total, passed, failed, pass_rate |

### environment 维度

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"checked"` or `"skipped"` |
| `score` | float | fitness_score |
| `dependencies[]` | object[] | 依赖项列表 |
| `summary` | object | 分类计数 + fitness_score |

### dependency 对象

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | yes | `tool` / `capability` / `external_service` / `implicit` |
| `name` | string | yes | 短标识符（也用于 frontmatter dependencies） |
| `description` | string | yes | 需要什么、为什么 |
| `evidence` | string | yes | SKILL.md 原文引用 |
| `compatibility` | string | yes | `compatible` / `adaptable` / `incompatible` / `unknown` |
| `reason` | string | yes | 分类理由 |
| `adaptation` | object | no | 适配方案（adaptable 项） |
| `adaptation.target_capability` | string | yes* | 替代能力 |
| `adaptation.strategy` | string | yes* | `replace` / `wrap` / `degrade` / `remove` |
| `adaptation.description` | string | yes* | 改什么、为什么 |
| `adaptation.changes` | string[] | yes* | 具体的 SKILL.md 修改 |

\* Required when `adaptation` is present.

### optimization 对象

| Field | Type | Description |
|-------|------|-------------|
| `iterations[]` | object[] | 每轮记录：iteration, description, train_passed, train_total |
| `best.description` | string | 最优 description |
| `best.test_score` | float | test set 最终得分 |
