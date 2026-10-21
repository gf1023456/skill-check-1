#!/usr/bin/env python
"""
续航测试数据分析脚本

支持输入续航测试数据（包括使用时间、电量变化等），统计并生成续航分析报告。

用法示例：
    python analyze_battery_test.py --data "{\"phone\": \"iPhone 15 Pro\", \"battery_capacity\": 3274, \"tests\": [{\"scenario\": \"视频播放\", \"duration_hours\": 1, \"battery_drain\": 12}, {\"scenario\": \"游戏\", \"duration_hours\": 1, \"battery_drain\": 25}]}"
"""

import argparse
import json
from typing import Dict
from datetime import datetime


def analyze_battery(data: Dict) -> Dict:
    """
    分析续航测试数据
    
    Args:
        data: 包含电池容量和测试数据的字典
        
    Returns:
        分析结果字典
    """
    phone_name = data.get('phone', '未知手机')
    battery_capacity = data.get('battery_capacity', 0)
    tests = data.get('tests', [])
    
    if not battery_capacity or not tests:
        return {"error": "数据不完整，需要battery_capacity和tests字段"}
    
    # 计算各场景的续航估计
    results = {
        "phone": phone_name,
        "battery_capacity": battery_capacity,
        "test_count": len(tests),
        "scenarios": [],
        "summary": {}
    }
    
    total_drain = 0
    total_hours = 0
    
    for test in tests:
        scenario = test.get('scenario', '未知场景')
        duration = test.get('duration_hours', 0)
        drain = test.get('battery_drain', 0)
        
        # 估算每小时耗电百分比
        hourly_drain = drain / duration if duration > 0 else 0
        
        # 估算总续航时间（假设100%电量）
        estimated_battery_life = 100 / hourly_drain if hourly_drain > 0 else 0
        
        scenario_result = {
            "scenario": scenario,
            "duration_hours": duration,
            "battery_drain_percent": drain,
            "hourly_drain_percent": round(hourly_drain, 2),
            "estimated_battery_life_hours": round(estimated_battery_life, 1)
        }
        
        results["scenarios"].append(scenario_result)
        
        total_drain += drain
        total_hours += duration
    
    # 综合统计
    avg_hourly_drain = total_drain / total_hours if total_hours > 0 else 0
    overall_battery_life = 100 / avg_hourly_drain if avg_hourly_drain > 0 else 0
    
    results["summary"] = {
        "total_test_hours": total_hours,
        "total_battery_drain": total_drain,
        "avg_hourly_drain": round(avg_hourly_drain, 2),
        "estimated_overall_battery_life_hours": round(overall_battery_life, 1),
        "battery_health_score": calculate_battery_health(battery_capacity, avg_hourly_drain)
    }
    
    return results


def calculate_battery_health(capacity: int, hourly_drain: float) -> int:
    """
    计算电池健康评分（0-100）
    
    Args:
        capacity: 电池容量(mAh)
        hourly_drain: 每小时耗电百分比
        
    Returns:
        健康评分
    """
    # 参考标准：现代旗舰手机平均每小时耗电约5-8%
    # 低于5%为优秀，5-8%为良好，8-12%为一般，超过12%为较差
    
    if hourly_drain <= 0:
        return 100
    
    if hourly_drain <= 5:
        return 95
    elif hourly_drain <= 8:
        return 85
    elif hourly_drain <= 12:
        return 70
    else:
        return 50


def generate_markdown_report(analysis: Dict) -> str:
    """
    生成Markdown格式的续航分析报告
    
    Args:
        analysis: 分析结果
        
    Returns:
        Markdown格式报告
    """
    if 'error' in analysis:
        return f"# 续航分析报告\n\n错误：{analysis['error']}\n"
    
    lines = [
        "# 续航测试分析报告",
        "",
        f"**手机型号**：{analysis['phone']}",
        f"**电池容量**：{analysis['battery_capacity']}mAh",
        f"**测试场景数**：{analysis['test_count']}",
        "",
        "## 各场景测试结果",
        "",
        "| 场景 | 测试时长(小时) | 耗电(%) | 每小时耗电(%) | 预估续航(小时) |",
        "|------|---------------|---------|---------------|---------------|"
    ]
    
    for scenario in analysis['scenarios']:
        lines.append(
            f"| {scenario['scenario']} | {scenario['duration_hours']} | "
            f"{scenario['battery_drain_percent']} | {scenario['hourly_drain_percent']} | "
            f"{scenario['estimated_battery_life_hours']} |"
        )
    
    summary = analysis['summary']
    lines.extend([
        "",
        "## 综合评估",
        "",
        f"- 总测试时长：{summary['total_test_hours']}小时",
        f"- 总耗电：{summary['total_battery_drain']}%",
        f"- 平均每小时耗电：{summary['avg_hourly_drain']}%",
        f"- 预估总续航：{summary['estimated_overall_battery_life_hours']}小时",
        f"- 电池健康评分：{summary['battery_health_score']}/100",
        "",
        "## 结论",
        "",
    ])
    
    # 添加结论建议
    health = summary['battery_health_score']
    if health >= 90:
        lines.append("电池续航表现优秀，日常使用无需担心。")
    elif health >= 80:
        lines.append("电池续航表现良好，重度使用可能需要携带充电宝。")
    elif health >= 70:
        lines.append("电池续航表现一般，建议关注电量使用情况。")
    else:
        lines.append("电池续航表现较差，建议考虑更换电池或减少重度使用。")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='续航测试数据分析工具')
    parser.add_argument('--data', type=str, required=True, help='JSON格式的测试数据')
    parser.add_argument('--output', type=str, help='输出Markdown文件路径')
    
    args = parser.parse_args()
    
    try:
        # 解析JSON数据
        data = json.loads(args.data)
        
        # 分析数据
        analysis = analyze_battery(data)
        
        # 生成报告
        report = generate_markdown_report(analysis)
        
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
