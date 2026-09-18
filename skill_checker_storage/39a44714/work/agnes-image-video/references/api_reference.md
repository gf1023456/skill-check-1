# Agnes AI API 详细参考文档

## API 基础信息

### 端点地址
- **Base URL**: `https://apihub.agnes-ai.com/v1`
- **认证方式**: Bearer Token
- **协议兼容**: OpenAI Compatible API

### 认证

所有请求需要在 Header 中携带 API Key：
```
Authorization: Bearer your-api-key
```

### 获取 API Key
1. 访问 `platform.agnes-ai.com`
2. 注册/登录账号
3. 在控制台创建 API Key

---

## 图像生成接口

### 端点
```
POST https://apihub.agnes-ai.com/v1/images/generations
```

### 请求参数

#### 文生图 (agnes-image-2.1-flash)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 固定为 `agnes-image-2.1-flash` |
| prompt | string | 是 | 图片描述，支持中文 |
| size | string | 否 | 图片尺寸，默认 `1024x1024` |
| n | integer | 否 | 生成数量，默认 1 |

**重要限制**:
- **禁止**在纯文生图时传入 `extra_body` 参数，否则会抛出 `UnsupportedParamsError`
- Prompt 完全支持中文，无需翻译

**请求示例**:
```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "一只可爱的柴犬在樱花树下睡觉，温暖的阳光，柔和的粉色花瓣飘落",
  "size": "1024x1024",
  "n": 1
}
```

**响应示例**:
```json
{
  "data": [
    {
      "url": "https://...",
      "index": 0
    }
  ]
}
```

#### 图生图/编辑 (agnes-image-2.0-flash)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 固定为 `agnes-image-2.0-flash` |
| prompt | string | 是 | 编辑指令 |
| size | string | 否 | 输出图片尺寸 |
| extra_body.tags | array | 是 | 必须包含 `["img2img"]` |
| extra_body.image | array | 是 | 输入图片 URL 数组 |
| extra_body.response_format | string | 否 | 输出格式：`"url"` 或 `"b64_json"` |

**请求示例**:
```json
{
  "model": "agnes-image-2.0-flash",
  "prompt": "改成水彩画风格",
  "size": "1024x768",
  "extra_body": {
    "tags": ["img2img"],
    "image": ["https://example.com/photo.png"],
    "response_format": "url"
  }
}
```

**响应示例**:
```json
{
  "data": [
    {
      "url": "https://...",
      "index": 0
    }
  ]
}
```

---

## 视频生成接口

### 端点
```
POST https://apihub.agnes-ai.com/v1/videos/generations
GET  https://apihub.agnes-ai.com/v1/videos/{task_id}
```

### 视频生成流程

视频生成采用**异步任务**模式，需要两步完成：

1. **创建任务** (POST): 提交视频生成请求，获取 task_id
2. **查询状态** (GET): 轮询 task_id 获取生成结果

### Step 1: 创建任务

**端点**: `POST https://apihub.agnes-ai.com/v1/videos/generations`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 固定为 `agnes-video-v2.0` |
| prompt | string | 是 | 视频描述（**建议英文**） |
| width | integer | 否 | 视频宽度，默认 1152 |
| height | integer | 否 | 视频高度，默认 768 |
| num_frames | integer | 否 | 帧数，≤441，格式需满足 `8n+1` |
| frame_rate | integer | 否 | 帧率，范围 1-60 |

**帧数配置建议**:

| 视频时长 | num_frames | frame_rate | 计算 |
|----------|------------|------------|------|
| ~5 秒 | 121 | 24 | 121/24 ≈ 5.04 |
| ~10 秒 | 241 | 24 | 241/24 ≈ 10.04 |
| ~18 秒 | 441 | 24 | 441/24 ≈ 18.38 |

**时长计算公式**: `seconds = num_frames / frame_rate`

**请求示例**:
```json
{
  "model": "agnes-video-v2.0",
  "prompt": "Shiba Inu under cherry blossom tree, petals falling, warm sunlight",
  "width": 1152,
  "height": 768,
  "num_frames": 121,
  "frame_rate": 24
}
```

**响应示例**:
```json
{
  "id": "task_xxx",
  "status": "processing",
  "created_at": 1234567890
}
```

### Step 2: 查询状态

**端点**: `GET https://apihub.agnes-ai.com/v1/videos/{task_id}`

**响应状态**:

| 状态 | 说明 |
|------|------|
| `processing` | 生成中 |
| `completed` | 生成完成 |
| `failed` | 生成失败 |

**完成时响应示例**:
```json
{
  "id": "task_xxx",
  "status": "completed",
  "remixed_from_video_id": "https://video-url.com/video.mp4"
}
```

**⚠️ 重要注意事项**:
1. **字段名不一致**: 视频 URL 字段实际名为 `remixed_from_video_id`，而非 `video_url`
2. 代码中应做兼容处理：`result.get("video_url") or result.get("remixed_from_video_id")`
3. 建议轮询间隔：5-10 秒
4. 视频生成耗时：约 2-3 分钟（3-5 秒视频）

### 视频特性

- **音频**: 视频自动生成 AAC 格式音频
- **语音支持**: 支持中英文对话
- **语音生成**: 在 prompt 中描述具体台词可尝试生成对应语音，但模型可能根据场景理解生成，不一定 100% 复述指定文字
- **示例**: `prompt="A person saying 'Welcome'"` 可能生成带语音的视频

---

## 错误处理

### 常见错误

1. **UnsupportedParamsError**: 文生图时传入了 `extra_body`
   - **解决**: 纯文生图不要传 `extra_body`

2. **认证失败**: API Key 无效或过期
   - **解决**: 检查 API Key 是否正确

3. **参数错误**: `num_frames` 不符合 `8n+1` 格式
   - **解决**: 使用推荐的帧数配置（121, 241, 441）

### 错误响应格式

```json
{
  "error": {
    "message": "错误信息",
    "type": "InvalidRequestError",
    "param": null,
    "code": null
  }
}
```

---

## Python SDK 使用

### 安装依赖

```bash
pip install openai
```

### 完整示例

```python
from openai import OpenAI
import time

# 初始化客户端
client = OpenAI(
    api_key="your-api-key",
    base_url="https://apihub.agnes-ai.com/v1"
)

# 文生图
def generate_image(prompt, size="1024x1024"):
    response = client.images.generate(
        model="agnes-image-2.1-flash",
        prompt=prompt,
        size=size
    )
    return response.data[0].url

# 图生图
def edit_image(prompt, image_url, size="1024x768"):
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
    return response.data[0].url

# 文生视频
def generate_video(prompt, width=1152, height=768, num_frames=121, frame_rate=24):
    # 创建任务
    response = client.video.create(
        model="agnes-video-v2.0",
        prompt=prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        frame_rate=frame_rate
    )
    task_id = response.id
    
    # 轮询状态
    while True:
        status = client.video.retrieve(task_id)
        if status.status == "completed":
            # 兼容处理字段名
            video_url = status.get("video_url") or status.get("remixed_from_video_id")
            return video_url
        time.sleep(5)
```

---

## JavaScript/Node.js SDK 使用

### 安装依赖

```bash
npm install openai
```

### 完整示例

```javascript
const OpenAI = require('openai');

const client = new OpenAI({
  apiKey: 'your-api-key',
  baseURL: 'https://apihub.agnes-ai.com/v1'
});

// 文生图
async function generateImage(prompt) {
  const response = await client.images.generate({
    model: 'agnes-image-2.1-flash',
    prompt: prompt,
    size: '1024x1024'
  });
  return response.data[0].url;
}

// 文生视频（异步）
async function generateVideo(prompt) {
  // 创建任务
  const response = await client.video.create({
    model: 'agnes-video-v2.0',
    prompt: prompt,
    width: 1152,
    height: 768,
    num_frames: 121,
    frame_rate: 24
  });
  const taskId = response.id;
  
  // 轮询状态
  while (true) {
    const status = await client.video.retrieve(taskId);
    if (status.status === 'completed') {
      const videoUrl = status.video_url || status.remixed_from_video_id;
      return videoUrl;
    }
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}
```

---

## 性能指标

| 功能 | 模型 | 耗时 | 质量 |
|------|------|------|------|
| 文生图 | agnes-image-2.1-flash | ~5 秒 | 优秀 |
| 图生图 | agnes-image-2.0-flash | ~5-10 秒 | 良好 |
| 文生视频 | agnes-video-v2.0 | 2-3 分钟 | 良好 |

## 限制与约束

1. **并发限制**: 暂无明确限制（免费 API）
2. **速率限制**: 暂无明确限制（免费 API）
3. **图片尺寸**: 支持常见比例，建议 1024x1024、1024x768、768x1024
4. **视频时长**: 最短 ~5 秒，最长 ~18 秒
5. **语言支持**: Prompt 支持中文和英文

---

## 参考资料

- 官方平台: `platform.agnes-ai.com`
- API 文档: `apihub.agnes-ai.com/v1`
- 模型列表:
  - `agnes-2.0-flash` (文本对话)
  - `agnes-image-2.1-flash` (文生图)
  - `agnes-image-2.0-flash` (图生图/编辑)
  - `agnes-video-v2.0` (文生视频)
