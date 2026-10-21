---
name: phone-review-assistant
description: AI 辅助手机评测，支持手机规格参数解析、跑分数据对比、拍照样张分析、续航测试记录，并输出 Markdown 格式的评测报告
---

# phone-review-assistant：AI 辅助手机评测与报告生成

## Overview

使用 **phone-review-assistant** 来解析手机规格参数、对比跑分数据、分析拍照样张、记录续航测试，并自动生成结构化的 Markdown 评测报告。该技能将分散的评测数据整合为专业、可读的报告，显著提升评测效率与一致性。

## When to Use

✅ **USE** 当需要：
- 从厂商官网或新闻稿中提取手机规格（如处理器、屏幕、电池等）并整理为表格
- 对比多款手机的跑分数据（如 Geekbench、Antutu）并生成对比图表或表格
- 分析拍照样张的 EXIF 信息、缩略图质量或进行基础图像质量评估（如亮度、噪点）
- 记录续航测试的时长、使用场景、电量变化，并计算平均功耗
- 生成完整的 Markdown 评测报告，包含上述所有数据和分析结论

❌ **DON'T USE** 当需要：
- 进行主观体验评价（如手感、外观设计）——此技能只处理客观数据
- 执行复杂的图像处理（如专业降噪、HDR 合成）——建议使用专业图像工具
- 访问付费跑分数据库或实时在线数据——技能仅处理已有数据或本地文件
- 生成最终发布用的视频脚本——技能专注于文字报告

## Quick Start

**场景**：快速生成一款手机的规格解析报告。

```bash
# 假设你已获取手机规格文本（如从官网复制）
cat specs.txt | phone-review-assistant parse-specs --format markdown
```

**输出**：
```markdown
| 参数 | 值 |
|------|-----|
| 处理器 | Snapdragon 8 Gen 2 |
| 屏幕 | 6.7" OLED, 120Hz |
| 电池 | 5000mAh |
| ... | ... |
```

## Common Operations

### 1. 解析手机规格参数

从非结构化文本中提取关键规格，并输出为结构化表格。

```bash
phone-review-assistant parse-specs --input specs.txt --output specs.md
```

**为什么**：人工阅读长文本易遗漏细节，自动化提取确保关键参数（如芯片、存储、摄像头）不丢失，且格式统一。

**技巧**：支持常见单位（如英寸、mAh、GHz）自动标准化。若提取不完整，可手动补充后重新运行。

### 2. 对比跑分数据

对比多款手机的跑分数据，生成对比表格或条形图（Markdown 格式）。

```bash
phone-review-assistant compare-benchmarks --data geekbench.csv --metrics single,multi --output compare.md
```

**为什么**：跑分对比是性能评估的核心，但原始数据难以直观理解。此操作自动排序并突出最高分，帮助快速定位性能差异。

**注意**：支持 CSV 或 JSON 输入，每行/每对象代表一款手机，需包含 `model` 字段和至少一个分数指标。

### 3. 分析拍照样张

分析样张的 EXIF 信息和基础图像质量，生成分析摘要。

```bash
phone-review-assistant analyze-photos --dir ./samples --output photo-analysis.md
```

**为什么**：样张的 EXIF（如 ISO、快门速度）能反映拍摄条件，而基础质量指标（如亮度直方图、噪点水平）可客观评估成像能力，避免主观偏见。

**输出**：每个样张生成一节，包含 EXIF 表格和图像质量评分（0-100）。

**限制**：仅支持 JPEG/PNG 格式，且不进行语义理解（如场景识别）。

### 4. 记录续航测试

记录续航测试数据（时长、场景、电量变化），并计算平均功耗。

```bash
phone-review-assistant record-battery --log battery.csv --output battery.md
```

**为什么**：续航测试涉及多场景（如视频播放、游戏），手动计算功耗易出错。此操作自动计算每小时耗电百分比，并生成趋势表。

**输入格式**：CSV 列：`time, scenario, battery_percent`。

**输出**：包含每场景耗电速率、总时长和平均功耗的 Markdown 表格。

### 5. 生成完整评测报告

整合所有数据源，生成一篇结构化的 Markdown 评测报告。

```bash
phone-review-assistant generate-report --specs specs.md --benchmarks compare.md --photos photo-analysis.md --battery battery.md --output final-report.md
```

**为什么**：单独的数据文件分散，不便于阅读。此操作自动组合为统一报告，包含标题、摘要、各章节和结论，节省整理时间。

**报告结构**：
- 标题与简介
- 规格解析
- 性能跑分对比
- 拍照样张分析
- 续航测试记录
- 总结与建议

## Notes

- **数据格式**：所有输入文件推荐使用 UTF-8 编码，CSV 需包含表头。
- **单位标准化**：技能会自动标准化单位，但请确保原始数据格式正确（如"6.7英寸"而非"6.7 in"）。
- **样本数量**：拍照分析至少需要 3 张样张，否则会警告并降低置信度。
- **跑分对比**：若数据缺失，技能会跳过该指标并提示，不会中断流程。
- **报告定制**：可通过 `--template` 参数指定自定义报告模板（Jinja2 格式），便于品牌化。
- **错误处理**：遇到无法解析的文本时，技能会输出警告并跳过，但不会终止整个流程。
- **隐私注意**：样张分析会读取 EXIF 数据，可能包含 GPS 位置，建议在分享报告前清理敏感信息。
- **版本兼容**：确保使用最新版本，以获取最新的跑分数据库和图像分析算法。

---

## Resources

本技能包含以下资源文件：

### scripts/
可执行的 Python 脚本，用于自动化操作。

### references/
参考文档和 API 说明。

---

*此内容由 AI 辅助生成，请根据实际需求修改完善*