#!/usr/bin/env python
"""
手机规格参数解析脚本

支持从文本中提取手机的关键规格参数，包括处理器、内存、存储、屏幕、摄像头等。

用法示例：
    python parse_phone_specs.py --input "iPhone 15 Pro Max 256GB 钛金属"
    python parse_phone_specs.py --file specs.txt
"""

import argparse
import re
import json
from typing import Dict


def parse_specs(text: str) -> Dict[str, str]:
    """
    从文本中解析手机规格参数
    
    Args:
        text: 包含手机规格信息的文本
        
    Returns:
        包含解析结果的字典
    """
    specs = {}
    
    # 处理器解析 (例如: A17 Pro, Snapdragon 8 Gen 3, Dimensity 9300)
    processor_patterns = [
        r'([A-Z]\d+\s*Pro?)',  # A17 Pro
        r'(Snapdragon\s*\d+\s*Gen\s*\d+)',  # Snapdragon 8 Gen 3
        r'(Dimensity\s*\d+)',  # Dimensity 9300
        r'(Exynos\s*\d+)'  # Exynos 2400
    ]
    for pattern in processor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            specs['processor'] = match.group(1).strip()
            break
    
    # 内存解析 (例如: 8GB, 12GB, 16GB)
    ram_match = re.search(r'(\d+)GB\s*RAM', text, re.IGNORECASE)
    if ram_match:
        specs['ram'] = f"{ram_match.group(1)}GB"
    else:
        ram_match = re.search(r'(\d+)\s*GB(?!\s*存储)', text, re.IGNORECASE)
        if ram_match:
            specs['ram'] = f"{ram_match.group(1)}GB"
    
    # 存储解析 (例如: 128GB, 256GB, 512GB, 1TB)
    storage_match = re.search(r'(\d+)\s*GB|(\d+)TB', text, re.IGNORECASE)
    if storage_match:
        if storage_match.group(1):
            specs['storage'] = f"{storage_match.group(1)}GB"
        elif storage_match.group(2):
            specs['storage'] = f"{storage_match.group(2)}TB"
    
    # 屏幕尺寸解析 (例如: 6.1英寸, 6.7寸)
    screen_match = re.search(r'(\d+\.?\d*)\s*(?:英寸|寸|inch)', text, re.IGNORECASE)
    if screen_match:
        specs['screen_size'] = f"{screen_match.group(1)}英寸"
    
    # 摄像头像素解析 (例如: 48MP, 108MP, 5000万像素)
    camera_match = re.search(r'(\d+)\s*(?:MP|百万像素)', text, re.IGNORECASE)
    if camera_match:
        specs['camera'] = f"{camera_match.group(1)}MP"
    
    # 电池容量解析 (例如: 5000mAh, 4500毫安)
    battery_match = re.search(r'(\d+)\s*(?:mAh|毫安)', text, re.IGNORECASE)
    if battery_match:
        specs['battery'] = f"{battery_match.group(1)}mAh"
    
    return specs


def main():
    parser = argparse.ArgumentParser(description='手机规格参数解析工具')
    parser.add_argument('--input', type=str, help='直接输入的规格文本')
    parser.add_argument('--file', type=str, help='从文件读取规格文本')
    parser.add_argument('--output', type=str, help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    try:
        # 获取输入文本
        if args.input:
            text = args.input
        elif args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            parser.error('请提供 --input 或 --file 参数')
        
        # 解析规格
        specs = parse_specs(text)
        
        # 输出结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(specs, f, ensure_ascii=False, indent=2)
            print(f'解析结果已保存到 {args.output}')
        else:
            print(json.dumps(specs, ensure_ascii=False, indent=2))
            
    except Exception as e:
        print(f'错误: {e}')


if __name__ == '__main__':
    main()
