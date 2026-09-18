---
name: agnes-image-video
description: 使用 Agnes AI 的全模态 API 进行文生图、图生图、图片编辑和文生视频生成。支持 agnes-image-2.1-flash（文生图）、agnes-image-2.0-flash（图生图/编辑）和 agnes-video-v2.0（视频生成）模型。当用户需要生成图片、编辑图片、风格转换或创建视频时使用此 skill。
---

# Agnes AI 图像与视频生成 Skill

## 概述

此 skill 提供对 Agnes AI 全模态 API 的完整访问能力，包括图像生成、图像编辑和视频生成功能。API 完全免费且无限期开放，采用 OpenAI 兼容协议。

## 基础配置

### 连接参数

- **平台地址**: `platform.agnes-ai.com`
- **认证方式**: Bearer Token (API Key)
- **Base URL**: `https://apihub.agnes-ai.com/v1`
- **兼容性**: OpenAI 兼容协议

### 模型选择

| 模型 | 功能 | 说明 |
|------|------|------|
| `agnes-image-2.1-flash` | 文生图 (Text-to-Image) | 高质量图像生成，支持中文 prompt，约 5 秒出图 |
| `agnes-image-2.0-flash` | 图生图/图片编辑 (Image-to-Image) | 风格转换、图片编辑、多图合成 |
| `agnes-video-v2.0` | 文生视频 (Text-to-Video) | 异步任务，生成 3-5 秒视频，约 2-3 分钟 |

## 工作流程

### 文生图 (Text-to-Image)

使用 `agnes-image-2.1-flash` 模型从文本描述生成图像。

**关键限制**:
- **不要**在纯文生图时传入 `extra_body.response_format`，会报错
- Prompt 完全支持中文，无需翻译
- 默认输出尺寸为 1024x1024

**示例代码**:

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key",
    base_url="https://apihub.agnes-ai.com/v1"
)

# 文生图
response = client.images.generate(
    model="agnes-image-2.1-flash",
    prompt="一只可爱的柴犬在樱花树下睡觉，温暖的阳光，柔和的粉色花瓣飘落",
    size="1024x1024"
)

# 获取图片 URL
image_url = response.data[0].url
```

### 图生图/图片编辑 (Image-to-Image)

使用 `agnes-image-2.0-flash` 模型对现有图片进行修改、风格转换。

**关键限制**:
- **必须**通过 `extra_body` 传递图片 URL 和标签
- 需要设置 `extra_body["tags"] = ["img2img"]`
- 可以使用 `extra_body["response_format"]` 指定输出格式（`"url"` 或 `"b64_json"`）

**示例代码**:

```python
# 图生图 - 风格转换
response = client.images.generate(
    model="agnes-image-2.0-flash",
    prompt="改成水彩画风格",
    size="1024x768",
    extra_body={
        "tags": ["img2img"],
        "image": ["https://example.com/photo.png"],
        "response_format": "url"
    }
)

image_url = response.data[0].url
```

### 文生视频 (Text-to-Video)

使用 `agnes-video-v2.0` 模型从文本描述生成视频。这是**异步任务**，需要两步完成。

**核心参数**:
- `prompt`: 视频描述（**建议使用英文**）
- `width` / `height`: 分辨率（默认 1152x768）
- `num_frames`: 帧数（≤441，格式需满足 `8n+1`）
- `frame_rate`: 帧率（范围 1-60）

**时长计算公式**: `seconds = num_frames / frame_rate`

**常见配置**:
- ~5 秒视频: `num_frames=121`, `frame_rate=24`
- ~10 秒视频: `num_frames=241`, `frame_rate=24`
- ~18 秒视频: `num_frames=441`, `frame_rate=24`

**示例代码**:

```python
import time

# Step 1: 创建视频生成任务
response = client.video.create(
    model="agnes-video-v2.0",
    prompt="Shiba Inu under cherry blossom tree, petals falling",
    width=1152,
    height=768,
    num_frames=121,
    frame_rate=24
)
task_id = response.id

# Step 2: 轮询任务状态
while True:
    status_response = client.video.retrieve(task_id)
    if status_response.status == "completed":
        # ⚠️ 注意：字段名是 remixed_from_video_id 而非 video_url
        video_url = status_response.get("video_url") or status_response.get("remixed_from_video_id")
        print(f"Video URL: {video_url}")
        break
    time.sleep(5)  # 等待 5 秒后再次查询
```

**关键注意事项**:
- 视频生成约需 2-3 分钟
- 视频自动生成 AAC 音频，支持中英文对话
- 在 prompt 中描述具体台词可尝试生成对应语音，但不保证 100% 准确
- API 响应中视频 URL 字段名为 `remixed_from_video_id`，代码需兼容处理

## 执行步骤

1. **确认用户需求**: 明确用户需要生成图片、编辑图片还是创建视频
2. **获取 API Key**: 确保已配置 Agnes AI 的 API Key（从 platform.agnes-ai.com 获取）
3. **选择合适模型**:
   - 纯文本生成图片 → `agnes-image-2.1-flash`
   - 修改现有图片 → `agnes-image-2.0-flash`
   - 创建视频 → `agnes-video-v2.0`
4. **构建请求参数**: 根据功能类型正确设置参数（注意上述关键限制）
5. **执行 API 调用**: 调用对应接口并处理响应
6. **返回结果**: 返回生成的图片或视频 URL

## 常见使用场景

- "帮我生成一张XX的图片" → 文生图
- "把这张图改成XX风格" → 图生图
- "编辑这张图片，XX" → 图片编辑
- "生成一段XX的视频" → 文生视频

## 参考资源

详细 API 文档和更多示例请参考 `references/api_reference.md`。
