#!/usr/bin/env python
"""
跑分数据对比与报告生成脚本

支持输入多个手机的跑分数据，进行对比分析，并生成Markdown格式的对比报告。

用法示例：
    python generate_benchmark_report.py --data "{\"iPhone 15 Pro\": {\"安兔兔\": 1640000, \"Geekbench\": 2900}, \"小米14\": {\"安兔兔\": 2000000, \"Geekbench\": 2200}}" --output report.md
"""

import argparse
import json
from typing import Dict
from datetime import datetime


def generate_report(data: Dict[str, Dict[str, float]]) -> str:
    """
    生成跑分对比的Markdown报告
    
    Args:
        data: 手机跑分数据，格式为 {手机名: {测试项目: 分数}}
        
    Returns:
        Markdown格式的报告内容
    """
    if not data:
        return "# 跑分对比报告\n\n暂无数据\n"
    
    # 获取所有测试项目
    all_benchmarks = set()
    for phone_data in data.values():
        all_benchmarks.update(phone_data.keys())
    all_benchmarks = sorted(all_benchmarks)
    
    # 生成报告
    report_lines = [
        "# 手机跑分对比报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 对比数据",
        "",
        "| 手机型号 | " + " | ".join(all_benchmarks) + " |",
        "|---------|" + "|".join(["---"] * len(all_benchmarks)) + "|"
    ]
    
    # 添加数据行
    for phone, benchmarks in data.items():
        row = [f"**{phone}**"]
        for benchmark in all_benchmarks:
            score = benchmarks.get(benchmark, 'N/A')
            row.append(f"{score}")
        report_lines.append("| " + " | ".join(row) + " |")
    
    # 添加分析
    report_lines.extend(["", "## 分析", ""])
    
    # 计算各项目最高分
    for benchmark in all_benchmarks:
        scores = {phone: data[phone][benchmark] for phone in data if benchmark in data[phone]}
        if scores:
            best_phone = max(scores, key=scores.get)
            best_score = scores[best_phone]
            report_lines.append(f"- **{benchmark}** 最佳：{best_phone}（{best_score}分）")
    
    # 计算综合得分（平均值）
    report_lines.extend(["", "### 综合表现（平均分）", ""])
    avg_scores = {}
    for phone, benchmarks in data.items():
        if benchmarks:
            avg = sum(benchmarks.values()) / len(benchmarks)
            avg_scores[phone] = avg
    
    if avg_scores:
        for phone, avg in sorted(avg_scores.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {phone}: {avg:.0f}分")
    
    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(description='跑分数据对比与报告生成')
    parser.add_argument('--data', type=str, required=True, help='JSON格式的跑分数据')
    parser.add_argument('--output', type=str, help='输出Markdown文件路径，默认输出到stdout')
    
    args = parser.parse_args()
    
    try:
        # 解析JSON数据
        data = json.loads(args.data)
        
        # 验证数据格式
        if not isinstance(data, dict):
            raise ValueError("数据必须是JSON对象格式")
        
        # 生成报告
        report = generate_report(data)
        
        # 输出结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f'报告已保存到 {args.output}')
        else:
            print(report)
            
    except json.JSONDecodeError as e:
        print(f'JSON解析错误: {e}')
    except Exception as e:
        print(f'错误: {e}')


if __name__ == '__main__':
    main()
