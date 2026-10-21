#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agnes AI 图像与视频生成工具集

提供文生图、图生图和文生视频的完整功能示例。

使用方式:
    python agnes_tool.py image "一只可爱的柴犬"
    python agnes_tool.py edit-image "改成水彩画风格" "https://example.com/photo.png"
    python agnes_tool.py video "Shiba Inu under cherry blossom tree"
"""

import argparse
import time
import sys
import os
import io
from pathlib import Path

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_client():
    """获取 OpenAI 客户端实例"""
    from openai import OpenAI
    
    # 优先从环境变量读取 API Key
    api_key = os.environ.get("AGNES_API_KEY", "sk-Trm30X87bxMW7LKxCMNtAec3IblPiyt4xY2Lr1PAhv0M1hqq")
    
    if api_key.startswith("sk-"):
        print("OK API Key configured")
    else:
        print("WARNING: API Key not configured!")
        print("Please configure via:")
        print("  1. Set environment variable: export AGNES_API_KEY='your-key'")
        print("  2. Or modify the api_key value in this script directly")
        print()
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://apihub.agnes-ai.com/v1",
        timeout=120  # 增加超时时间到 2 分钟
    )
    return client


def generate_image(client, prompt, size="1024x1024", output_dir="output"):
    """
    文生图: 从文本描述生成图片
    
    Args:
        client: OpenAI 客户端
        prompt: 图片描述（支持中文）
        size: 图片尺寸，默认 1024x1024
        output_dir: 输出目录
    
    Returns:
        str: 生成的图片 URL
    """
    print(f"🎨 正在生成图片...")
    print(f"   Prompt: {prompt}")
    print(f"   尺寸: {size}")
    print(f"   模型: agnes-image-2.1-flash")
    print()
    
    try:
        # ⚠️ 文生图不要传 extra_body
        response = client.images.generate(
            model="agnes-image-2.1-flash",
            prompt=prompt,
            size=size
        )
        
        image_url = response.data[0].url
        print(f"✅ 图片生成成功!")
        print(f"   URL: {image_url}")
        
        # 下载图片到本地
        img_path = download_image(client, image_url, output_dir)
        if img_path:
            print(f"   本地路径: {img_path}")
        
        return image_url
        
    except Exception as e:
        print(f"❌ 图片生成失败: {e}")
        return None


def edit_image(client, prompt, image_url, size="1024x768", output_dir="output"):
    """
    图生图/图片编辑: 修改现有图片
    
    Args:
        client: OpenAI 客户端
        prompt: 编辑指令
        image_url: 输入图片 URL
        size: 输出尺寸
        output_dir: 输出目录
    
    Returns:
        str: 生成的图片 URL
    """
    print(f"🎨 正在编辑图片...")
    print(f"   指令: {prompt}")
    print(f"   原图: {image_url}")
    print(f"   尺寸: {size}")
    print(f"   模型: agnes-image-2.0-flash")
    print()
    
    try:
        # ⚠️ 图生图必须传 extra_body
        response = client.images.generate(
            model="agnes-image-2.0-flash",
            prompt=prompt,
            size=size,
            extra_body={
                "tags": ["img2img"],
                "image": [image_url],
                "response_format": "url"
            }
        )
        
        result_url = response.data[0].url
        print(f"✅ 图片编辑成功!")
        print(f"   URL: {result_url}")
        
        # 下载图片到本地
        img_path = download_image(client, result_url, output_dir)
        if img_path:
            print(f"   本地路径: {img_path}")
        
        return result_url
        
    except Exception as e:
        print(f"❌ 图片编辑失败: {e}")
        return None


def generate_video(client, prompt, width=1152, height=768, num_frames=121, frame_rate=24, output_dir="output"):
    """
    文生视频: 从文本描述生成视频（异步任务）
    
    Args:
        client: OpenAI 客户端
        prompt: 视频描述（建议英文）
        width: 视频宽度
        height: 视频高度
        num_frames: 帧数（≤441，格式需满足 8n+1）
        frame_rate: 帧率（1-60）
        output_dir: 输出目录
    
    Returns:
        str: 生成的视频 URL
    """
    # 计算视频时长
    duration = num_frames / frame_rate
    print(f"🎬 正在创建视频任务...")
    print(f"   Prompt: {prompt}")
    print(f"   分辨率: {width}x{height}")
    print(f"   帧数: {num_frames}")
    print(f"   帧率: {frame_rate}")
    print(f"   预计时长: ~{duration:.1f} 秒")
    print(f"   模型: agnes-video-v2.0")
    print()
    
    try:
        # Step 1: 创建任务
        response = client.video.create(
            model="agnes-video-v2.0",
            prompt=prompt,
            width=width,
            height=height,
            num_frames=num_frames,
            frame_rate=frame_rate
        )
        task_id = response.id
        print(f"📋 任务已创建: {task_id}")
        print(f"⏳ 视频生成中，约需 2-3 分钟...")
        print()
        
        # Step 2: 轮询状态
        max_wait_time = 300  # 最多等待 5 分钟
        wait_time = 0
        interval = 5  # 每 5 秒查询一次
        
        while wait_time < max_wait_time:
            time.sleep(interval)
            wait_time += interval
            
            status_response = client.video.retrieve(task_id)
            status = status_response.status
            
            if status == "completed":
                print(f"✅ 视频生成成功!")
                # ⚠️ 字段名是 remixed_from_video_id 而非 video_url
                video_url = None
                if hasattr(status_response, 'get'):
                    video_url = status_response.get("video_url") or status_response.get("remixed_from_video_id")
                
                if not video_url:
                    # 尝试直接从对象属性获取
                    video_url = getattr(status_response, 'video_url', None) or \
                               getattr(status_response, 'remixed_from_video_id', None)
                
                if video_url:
                    print(f"   URL: {video_url}")
                    
                    # 下载视频到本地
                    video_path = download_video(client, video_url, output_dir)
                    if video_path:
                        print(f"   本地路径: {video_path}")
                
                return video_url
                
            elif status == "failed":
                print(f"❌ 视频生成失败!")
                print(f"   状态: {status}")
                return None
                
            else:
                # processing 或其他状态
                elapsed = wait_time // 60
                remaining = max_wait_time - wait_time
                print(f"   ⏳ 等待中... (已等待 {elapsed} 分钟, 剩余约 {remaining // 60} 分钟)")
        
        print(f"❌ 视频生成超时 (>5 分钟)")
        return None
        
    except Exception as e:
        print(f"❌ 视频生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def download_image(client, url, output_dir="output"):
    """下载图片到本地"""
    try:
        import urllib.request
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 从 URL 提取文件名
        filename = url.split("/")[-1].split("?")[0]
        if not filename.endswith((".png", ".jpg", ".jpeg")):
            filename = f"image_{int(time.time())}.png"
        
        file_path = output_path / filename
        
        # 下载文件
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
        
        return str(file_path)
        
    except Exception as e:
        print(f"⚠️  下载图片失败: {e}")
        return None


def download_video(client, url, output_dir="output"):
    """下载视频到本地"""
    try:
        import urllib.request
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 从 URL 提取文件名
        filename = url.split("/")[-1].split("?")[0]
        if not filename.endswith((".mp4", ".mov")):
            filename = f"video_{int(time.time())}.mp4"
        
        file_path = output_path / filename
        
        print(f"💾 正在下载视频...")
        
        # 下载文件
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            block_size = 8192
            downloaded = 0
            
            with open(file_path, "wb") as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        print(f"   ⏳ 下载进度: {percent:.1f}%")
        
        return str(file_path)
        
    except Exception as e:
        print(f"⚠️  下载视频失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Agnes AI 图像与视频生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 文生图
  python agnes_tool.py image "一只可爱的柴犬在樱花树下"

  # 图生图/编辑
  python agnes_tool.py edit-image "改成水彩画风格" "https://example.com/photo.png"

  # 文生视频 (~5秒)
  python agnes_tool.py video "Shiba Inu under cherry blossom tree"

  # 文生视频 (~10秒)
  python agnes_tool.py video "Shiba Inu under cherry blossom tree" --num-frames 241 --frame-rate 24

  # 文生视频 (~18秒)
  python agnes_tool.py video "Shiba Inu under cherry blossom tree" --num-frames 441 --frame-rate 24
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 文生图
    image_parser = subparsers.add_parser("image", help="文生图")
    image_parser.add_argument("prompt", help="图片描述（支持中文）")
    image_parser.add_argument("--size", default="1024x1024", help="图片尺寸 (默认: 1024x1024)")
    image_parser.add_argument("--output-dir", default="output", help="输出目录")
    
    # 图生图/编辑
    edit_parser = subparsers.add_parser("edit-image", help="图生图/图片编辑")
    edit_parser.add_argument("prompt", help="编辑指令")
    edit_parser.add_argument("image-url", help="输入图片 URL")
    edit_parser.add_argument("--size", default="1024x768", help="输出尺寸 (默认: 1024x768)")
    edit_parser.add_argument("--output-dir", default="output", help="输出目录")
    
    # 文生视频
    video_parser = subparsers.add_parser("video", help="文生视频")
    video_parser.add_argument("prompt", help="视频描述（建议英文）")
    video_parser.add_argument("--width", type=int, default=1152, help="视频宽度 (默认: 1152)")
    video_parser.add_argument("--height", type=int, default=768, help="视频高度 (默认: 768)")
    video_parser.add_argument("--num-frames", type=int, default=121, help="帧数 (默认: 121, ~5秒)")
    video_parser.add_argument("--frame-rate", type=int, default=24, help="帧率 (默认: 24)")
    video_parser.add_argument("--output-dir", default="output", help="输出目录")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 获取客户端
    client = get_client()
    
    # 执行命令
    if args.command == "image":
        generate_image(client, args.prompt, args.size, args.output_dir)
        
    elif args.command == "edit-image":
        edit_image(client, args.prompt, args.image_url, args.size, args.output_dir)
        
    elif args.command == "video":
        generate_video(
            client,
            args.prompt,
            args.width,
            args.height,
            args.num_frames,
            args.frame_rate,
            args.output_dir
        )


if __name__ == "__main__":
    main()
