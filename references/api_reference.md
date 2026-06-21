# API 参考文档

本文档提供通义千问 Qwen-Image、Google Gemini Imagen、以及 Agens-AI 图片/视频 API 的详细参数说明。

## 0. 统一入口

当前项目已提供统一入口脚本:

```bash
python3 scripts/generate_media.py --provider <provider> --mode <mode> --prompt "<prompt>"
```

默认会自动加载项目根目录 `.env.local` 中的 API Key。

### 0.1 provider

- `qwen`
- `gemini`
- `agens`

### 0.2 mode

- `text-to-image`
- `image-to-image`
- `text-to-video`
- `image-to-video`
- `multi-image-video`
- `keyframe-video`

也支持简写:

- `t2i`
- `i2i`
- `t2v`
- `i2v`
- `m2v`
- `kfv`

### 0.3 示例

#### Qwen 文生图

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode t2i \
  --prompt "一只橘猫在窗边读书，阳光温暖，电影感"
```

#### Gemini 文生图

```bash
python3 scripts/generate_media.py \
  --provider gemini \
  --mode text-to-image \
  --prompt "A cozy reading corner with a cat and golden sunlight"
```

#### Agens-AI 图生图

```bash
python3 scripts/generate_media.py \
  --provider agens \
  --mode image-to-image \
  --prompt "Transform this scene into a cyberpunk rainy night while preserving the composition" \
  --image-url "https://example.com/input.png" \
  --no-download
```

#### Agens-AI 图生视频

```bash
python3 scripts/generate_media.py \
  --provider agens \
  --mode image-to-video \
  --prompt "The character slowly turns and smiles at the camera" \
  --image-url "https://example.com/input.png" \
  --num-frames 81 \
  --frame-rate 24 \
  --width 768 \
  --height 512 \
  --no-download
```

## 1. 通义千问 Qwen-Image API

### 1.1 基本信息

- **API 名称**: Qwen-Image (千问文生图)
- **服务商**: 阿里云百炼
- **文档地址**: https://help.aliyun.com/zh/model-studio/qwen-image-api
- **支持模型**:
  - `qwen-image-2.0-pro` - 最新的高质量模型(推荐)
  - `qwen-image-plus` - 增强版模型
  - `qwen-image` - 标准版模型

### 1.2 API 端点

**同步调用**:
- 北京地域: `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`
- 新加坡地域: `POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`

### 1.3 认证

使用 Bearer Token 方式认证:

```http
Authorization: Bearer <DASHSCOPE_API_KEY>
```

### 1.4 请求参数

#### 请求体结构

```json
{
  "model": "qwen-image-2.0-pro",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "text": "图片描述"
          }
        ]
      }
    ]
  },
  "parameters": {
    "size": "2048*2048",
    "n": 1,
    "prompt_extend": true,
    "watermark": false,
    "negative_prompt": "低分辨率,模糊",
    "seed": 12345
  }
}
```

#### 参数说明

| 参数 | 类型 | 必选 | 说明 | 默认值 |
|------|------|------|------|--------|
| **model** | string | 是 | 模型名称 | - |
| **input.messages** | array | 是 | 消息列表 | - |
| **input.messages[].role** | string | 是 | 消息角色,固定为 "user" | - |
| **input.messages[].content** | array | 是 | 消息内容 | - |
| **input.messages[].content[].text** | string | 是 | 图片描述(正向提示词) | - |
| **parameters.size** | string | 否 | 输出图像分辨率 | "1024*1024" |
| **parameters.n** | integer | 否 | 生成图片数量(1-6) | 1 |
| **parameters.prompt_extend** | boolean | 否 | 是否开启提示词智能改写 | true |
| **parameters.watermark** | boolean | 否 | 是否添加 "Qwen-Image" 水印 | false |
| **parameters.negative_prompt** | string | 否 | 负向提示词,排除不想要的内容 | - |
| **parameters.seed** | integer | 否 | 随机种子,用于控制生成结果 | - |

#### 支持的分辨率

不同模型支持的分辨率不同:

| 模型 | 支持分辨率 |
|------|-----------|
| qwen-image-2.0-pro | 1024*1024, 2048*2048, 512*512, 1536*1536 |
| qwen-image-plus | 1024*1024, 2048*2048 |
| qwen-image | 1024*1024 |

#### 提示词限制

- **正向提示词**: 最多 800 字符
- **负向提示词**: 最多 500 字符

### 1.5 响应参数

#### 成功响应

```json
{
  "output": {
    "choices": [
      {
        "message": {
          "content": [
            {
              "image": "https://dashscope-result-sh.oss-cn-shanghai.aliyuncs.com/xxx.png?Expires=xxx"
            }
          ]
        }
      }
    ]
  },
  "usage": {
    "image_count": 1,
    "width": 2048,
    "height": 2048
  },
  "request_id": "xxx"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| output.choices | array | 生成结果列表 |
| output.choices[].message.content[].image | string | 图片 URL (24小时内有效) |
| usage.image_count | integer | 实际生成的图片数量 |
| usage.width | integer | 图片宽度 |
| usage.height | integer | 图片高度 |
| request_id | string | 请求 ID |

### 1.6 错误代码

| HTTP 状态码 | 错误代码 | 说明 |
|-----------|---------|------|
| 400 | InvalidParameter | 参数错误 |
| 401 | InvalidApiKey | API Key 无效 |
| 403 | AccessDenied | 访问拒绝(权限不足) |
| 429 | QuotaExceeded | 配额超限 |
| 500 | InternalError | 服务器内部错误 |
| 503 | ServiceUnavailable | 服务不可用 |

### 1.7 使用示例

#### Python (requests)

```python
import requests
import json

url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
headers = {
    "Authorization": "Bearer <DASHSCOPE_API_KEY>",
    "Content-Type": "application/json"
}

payload = {
    "model": "qwen-image-2.0-pro",
    "input": {
        "messages": [
            {
                "role": "user",
                "content": [{"text": "一只坐着的橘黄色的猫"}]
            }
        ]
    },
    "parameters": {
        "size": "2048*2048",
        "n": 1,
        "prompt_extend": True,
        "watermark": False
    }
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()

image_url = result["output"]["choices"][0]["message"]["content"][0]["image"]
print(f"图片 URL: {image_url}")
```

#### Python (dashscope SDK)

```python
from dashscope import MultiModalConversation

response = MultiModalConversation.call(
    api_key="<DASHSCOPE_API_KEY>",
    model="qwen-image-2.0-pro",
    messages=[
        {
            "role": "user",
            "content": [{"text": "一只坐着的橘黄色的猫"}]
        }
    ],
    size="2048*2048",
    n=1,
    prompt_extend=True,
    watermark=False
)

image_url = response.output.choices[0].message.content[0].image
print(f"图片 URL: {image_url}")
```

---

## 2. Google Gemini Imagen API

### 2.1 基本信息

- **API 名称**: Imagen 3
- **服务商**: Google
- **文档地址**: https://ai.google.dev/gemini-api/docs/imagen-prompt-guide
- **支持模型**: `imagen-3.0-generate-002`

### 2.2 API 端点

```
POST https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict
```

### 2.3 认证

使用 API Key 方式认证:

```http
x-goog-api-key: <GOOGLE_API_KEY>
```

### 2.4 请求参数

#### 请求体结构

```json
{
  "instances": [
    {
      "prompt": "A serene landscape with a lake and mountains at sunset"
    }
  ],
  "parameters": {
    "sampleCount": 1
  }
}
```

#### 参数说明

| 参数 | 类型 | 必选 | 说明 | 默认值 |
|------|------|------|------|--------|
| instances | array | 是 | 请求实例列表 | - |
| instances[].prompt | string | 是 | 图片描述(推荐英文) | - |
| parameters | object | 否 | 生成参数 | - |
| parameters.sampleCount | integer | 否 | 生成图片数量(1-4) | 1 |

### 2.5 响应参数

#### 成功响应

```json
{
  "predictions": [
    {
      "bytesBase64String": "iVBORw0KGgoAAAANSUhEUgAA..."
    }
  ]
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| predictions | array | 生成结果列表 |
| predictions[].bytesBase64String | string | Base64 编码的图片数据 |

**注意**: Base64 数据需要解码后才能保存为图片文件。

### 2.6 错误代码

| HTTP 状态码 | 错误说明 |
|-----------|---------|
| 400 | 请求参数错误 |
| 401 | API Key 无效 |
| 403 | 权限不足或配额用尽 |
| 429 | 请求频率超限 |
| 500 | 服务器内部错误 |

### 2.7 使用示例

#### Python (requests)

```python
import requests
import json
import base64

url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict"
headers = {
    "Content-Type": "application/json",
    "x-goog-api-key": "<GOOGLE_API_KEY>"
}

payload = {
    "instances": [
        {"prompt": "A serene landscape with a lake and mountains at sunset"}
    ],
    "parameters": {
        "sampleCount": 1
    }
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()

# 解码 Base64 数据
image_data = result["predictions"][0]["bytesBase64String"]
image_bytes = base64.b64decode(image_data)

# 保存图片
with open("imagen_output.png", "wb") as f:
    f.write(image_bytes)

print("图片已保存: imagen_output.png")
```

---

## 3. Agens-AI 图片 API

以下内容基于 2026-06-03 读取的官方文档页 `agnes-image-21-flash`。

### 3.1 基本信息

- **API 名称**: Agnes Image 2.1 Flash
- **服务商**: Agens-AI
- **文档页**: https://agnes-ai.com/doc/agnes-image-21-flash
- **模型名**: `agnes-image-2.1-flash`
- **能力**: 文生图、图生图

### 3.2 API 端点

```http
POST https://apihub.agnes-ai.com/v1/images/generations
```

### 3.3 认证

使用 Bearer Token:

```http
Authorization: Bearer <AGENS_AI_API_KEY>
```

### 3.4 请求参数

#### 文生图

```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "A luminous floating city above a misty canyon at sunrise, cinematic realism",
  "size": "1024x768"
}
```

#### 图生图

```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "Transform the scene into a rain-soaked cyberpunk night with neon reflections while preserving the composition",
  "size": "1024x768",
  "extra_body": {
    "image": [
      "https://example.com/input-image.png"
    ],
    "response_format": "url"
  }
}
```

#### 参数说明

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 固定使用 `agnes-image-2.1-flash` |
| `prompt` | string | 是 | 正向提示词 |
| `size` | string | 否 | 输出尺寸，如 `1024x768` |
| `extra_body.image` | array[string] | 否 | 图生图输入图片 URL 列表 |
| `extra_body.response_format` | string | 否 | 文档示例使用 `url` |

### 3.5 响应说明

文档公开示例强调使用 `response_format: "url"` 返回图片链接。实际响应中应提取图片 URL 并及时下载保存。

### 3.6 当前脚本约定

- 环境变量支持:
  - 单 Key: `AGENS_AI_API_KEY` / `AGENS_API_KEY`
  - 多 Key: `AGENS_AI_API_KEYS` / `AGENS_API_KEYS`
- 脚本:
  - `scripts/generate_agens_image.py`

---

## 4. Agens-AI 视频 API

以下内容基于 2026-06-03 读取的官方文档页 `agnes-video-v20`。

### 4.1 基本信息

- **API 名称**: Agnes Video V2.0
- **服务商**: Agens-AI
- **文档页**: https://agnes-ai.com/doc/agnes-video-v20
- **模型名**: `agnes-video-v2.0`
- **能力**: 文生视频、图生视频、多图视频、关键帧视频

### 4.2 API 端点

#### 创建任务

```http
POST https://apihub.agnes-ai.com/v1/videos
```

#### 查询结果

```http
GET https://apihub.agnes-ai.com/v1/videos/{task_id}
```

### 4.3 认证

```http
Authorization: Bearer <AGENS_AI_API_KEY>
```

### 4.4 请求参数

#### 文生视频

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "A cinematic shot of a cat walking on the beach at sunset, soft ocean waves, warm golden lighting, realistic motion",
  "height": 768,
  "width": 1152,
  "num_frames": 121,
  "frame_rate": 24
}
```

#### 图生视频

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "The woman slowly turns around and looks back at the camera, natural facial expression, cinematic camera movement",
  "image": "https://example.com/image.png",
  "num_frames": 121,
  "frame_rate": 24
}
```

#### 多图视频

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "Create a smooth transformation scene between the two reference images, cinematic lighting, consistent character identity, natural motion",
  "extra_body": {
    "image": [
      "https://example.com/image1.png",
      "https://example.com/image2.png"
    ]
  },
  "num_frames": 121,
  "frame_rate": 24
}
```

#### 关键帧视频

```json
{
  "model": "agnes-video-v2.0",
  "prompt": "Generate a smooth cinematic transition between the keyframes, maintaining visual consistency and natural camera movement",
  "extra_body": {
    "image": [
      "https://example.com/keyframe1.png",
      "https://example.com/keyframe2.png"
    ],
    "mode": "keyframes"
  },
  "num_frames": 121,
  "frame_rate": 24
}
```

### 4.5 响应参数

#### 创建任务响应

```json
{
  "id": "task_YOUR_TASK_ID",
  "task_id": "task_YOUR_TASK_ID",
  "object": "video",
  "model": "agnes-video-v2.0",
  "status": "queued",
  "progress": 0,
  "created_at": 1780457477,
  "seconds": "10.0",
  "size": "1280x768"
}
```

#### 查询完成响应

```json
{
  "id": "task_YOUR_TASK_ID",
  "model": "agnes-video-v2.0",
  "object": "video",
  "status": "completed",
  "progress": 100,
  "seconds": "10.0",
  "size": "1280x768",
  "error": null,
  "remixed_from_video_id": "https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_xxxxxx.mp4"
}
```

说明: 文档文字提到 `video_url` 会在 `completed` 后可用，但示例最终响应里给出的字段是 `remixed_from_video_id`。当前脚本同时兼容两者。

### 4.6 约束

- `num_frames <= 441`
- `num_frames` 必须满足 `8n + 1`
- 视频时长公式: `seconds = num_frames / frame_rate`
- 状态流转: `queued` -> 处理中 -> `completed` / `failed`

### 4.7 当前脚本约定

- 环境变量支持:
  - 单 Key: `AGENS_AI_API_KEY` / `AGENS_API_KEY`
  - 多 Key: `AGENS_AI_API_KEYS` / `AGENS_API_KEYS`
- 脚本:
  - `scripts/generate_agens_video.py`

---

## 5. 多 API Key 轮询

当前 skill 已支持 Qwen、Gemini、Agens-AI 的多 API Key 轮询。

### 5.1 支持方式

- CLI 参数:
  - `--api-key` 传单个 Key
  - `--api-keys` 传多个 Key
- 环境变量:
  - Qwen: `DASHSCOPE_API_KEYS` / `QWEN_API_KEYS`
  - Gemini: `GOOGLE_API_KEYS` / `GEMINI_API_KEYS`
  - Agens-AI: `AGENS_AI_API_KEYS` / `AGENS_API_KEYS`

### 5.2 轮询策略

- 同一 provider 内按持久化 round-robin 选择起始 Key
- 遇到可重试错误时自动切换下一个 Key
- 成功后推进游标，供下次请求继续轮询

---

## 6. 本地配置文件与环境变量

### 6.0 推荐方式

推荐把 API Key 放在项目根目录 `.env.local`:

```bash
# Agens-AI
AGENS_AI_API_KEY=your-agens-key

# Qwen
DASHSCOPE_API_KEY=your-qwen-key

# Gemini
GOOGLE_API_KEY=your-gemini-key
```

说明:

- 脚本会自动加载 `.env.local`
- 模板文件见 `.env.local.example`
- `.env.local` 已加入 `.gitignore`
- 已存在的系统环境变量优先级更高，不会被 `.env.local` 覆盖
### 6.1 Qwen 配置

```bash
# 单 Key
export DASHSCOPE_API_KEY="sk-xxxxx"
export QWEN_API_KEY="sk-xxxxx"

# 多 Key(逗号/分号/换行分隔均可)
export DASHSCOPE_API_KEYS="sk-a,sk-b"
export QWEN_API_KEYS="sk-a,sk-b"

# 可选: 默认模型
export QWEN_MODEL="qwen-image-2.0-pro"
```

### 6.2 Gemini 配置

```bash
# 单 Key
export GOOGLE_API_KEY="AIxxxxx"
export GEMINI_API_KEY="AIxxxxx"

# 多 Key
export GOOGLE_API_KEYS="AIxxxx1,AIxxxx2"
export GEMINI_API_KEYS="AIxxxx1,AIxxxx2"
```

### 6.3 Agens-AI 配置

```bash
# 单 Key
export AGENS_AI_API_KEY="ag-xxxxx"
export AGENS_API_KEY="ag-xxxxx"

# 多 Key
export AGENS_AI_API_KEYS="ag-key-1,ag-key-2"
export AGENS_API_KEYS="ag-key-1,ag-key-2"
```

### 6.4 在 .env 文件中配置

在项目根目录创建 `.env` 文件:

```bash
# Qwen
DASHSCOPE_API_KEY=sk-xxxxx
DASHSCOPE_API_KEYS=sk-key-1,sk-key-2

# Gemini
GOOGLE_API_KEY=AIxxxxx
GOOGLE_API_KEYS=AIkey1,AIkey2

# Agens-AI
AGENS_AI_API_KEY=ag-xxxxx
AGENS_AI_API_KEYS=ag-key-1,ag-key-2
```

然后在 Python 中加载:

```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 7. 最佳实践

### 7.1 提示词编写

#### Qwen (中文优化)

- 使用具体、详细的描述
- 包含主体、环境、风格、光线等元素
- 示例: "一只橘黄色的猫坐在沙发上,阳光从窗户照进来,温馨的氛围,电影感,4K高清"

#### Gemini (英文优化)

- 使用英文提示词效果更好
- 参考 [Imagen 提示词指南](https://ai.google.dev/gemini-api/docs/imagen-prompt-guide)
- 示例: "A cozy living room scene with a golden retriever resting on a beige sofa, warm sunlight streaming through a window, cinematic lighting, photorealistic, 8K"

#### Agens-AI

- 文生图/文生视频直接描述主体、环境、运动、光线和镜头语言
- 图生图要明确“保留什么”和“改变什么”
- 多图/关键帧视频要明确起始场景、目标场景和过渡方式

### 7.2 参数选择

- **质量优先**: 使用 `qwen-image-2.0-pro` 或 `imagen-3.0-generate-002`
- **速度优先**: 使用 `qwen-image`
- **多图生成**: Qwen 最多生成 6 张,Gemini 最多 4 张
- **尺寸选择**: 2048*2048 适合海报,1024*1024 适合社交媒体
- **视频长度**: Agens-AI 通过 `num_frames / frame_rate` 控制时长

### 7.3 错误处理

1. **API Key 无效**: 检查 Key 是否正确,是否已激活
2. **配额不足**: 检查账户余额或升级套餐
3. **网络错误**: 检查代理设置,增加超时时间
4. **提示词过长**: 精简提示词或开启 prompt_extend
5. **视频参数不合法**: 检查 `num_frames <= 441` 且满足 `8n + 1`

### 7.4 成本控制

- 先用少量参数测试,确认效果后再批量生成
- Qwen URL 24小时后失效,及时下载
- Gemini 按调用量计费,注意监控使用量
- Agens-AI 视频为异步任务,长视频建议先短片段验证

---

**更新日期**: 2026-06-03
