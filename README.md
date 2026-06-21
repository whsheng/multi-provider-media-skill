# multi-provider-media-skill

Unified AI image and video generation for Codex and agent workflows.

`multi-provider-media-skill` is a Codex skill and CLI toolkit for generating images and videos through multiple providers with one unified interface. You can keep the same prompt and switch only `--provider` to compare output styles or route requests across Qwen, Gemini Imagen, Agens-AI, and Wuli.

中文简介：这是一个面向 Codex / Agent 工作流的多模型媒体生成 Skill 和命令行工具，核心作用是用统一命令接入多个 provider 来生成图片或视频。你可以保持同一段提示词不变，仅切换 `--provider`，直接对比 Qwen、Gemini Imagen、Agens-AI 和 Wuli 的生成效果。

## What This Skill Does | 这个 Skill 是做什么的

This skill solves a simple practical problem: multiple model providers, one command.

- Generate images with different providers using the same prompt
- Compare provider output quality, style, and prompt understanding
- Route image or video generation through a consistent CLI entrypoint
- Manage multiple API keys per provider from one local config file

这个 Skill 主要解决一件事：把多个模型服务商的生成能力统一到一个命令入口里。

- 用同一段提示词切换不同 provider 生成图片
- 快速比较不同 provider 的画风、稳定性和语义理解
- 用统一 CLI 调用图片和视频生成能力
- 在一个本地配置文件里管理多家 provider 的 API key

## Highlights | 项目亮点

- One CLI entrypoint for multiple providers: `scripts/generate_media.py`
- Same prompt, different providers, directly comparable outputs
- Unified routing across image and video workflows
- Built-in multi-key rotation for provider failover and quota balancing
- Automatic local env loading from `.env.local`
- Local output download by default, with URL-only mode where supported
- Bundled reference docs for API details and prompt writing

## Core Idea | 核心用法

Use the same command shape and change only the provider:

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode t2i \
  --prompt "怪物史诺克与美国自由女神庆祝和平"
```

```bash
python3 scripts/generate_media.py \
  --provider wuli \
  --mode t2i \
  --prompt "怪物史诺克与美国自由女神庆祝和平"
```

```bash
python3 scripts/generate_media.py \
  --provider agens \
  --mode t2i \
  --prompt "怪物史诺克与美国自由女神庆祝和平"
```

这样你就可以在同一个 Skill 下，直接横向比较不同 provider 对同一提示词的生成结果。

## Supported Providers | 支持的服务商

| Provider | Default model | Modes |
|---|---|---|
| Qwen | `qwen-image-2.0-pro` | `text-to-image` |
| Gemini Imagen | `imagen-3.0-generate-002` | `text-to-image` |
| Agens-AI | `agnes-image-2.1-flash` / `agnes-video-v2.0` | `text-to-image`, `image-to-image`, `text-to-video`, `image-to-video`, `multi-image-video`, `keyframe-video` |
| Wuli | `Qwen Image Turbo` / `通义万相 2.2 Turbo` | `text-to-image`, `image-to-image`, `text-to-video`, `image-to-video`, `multi-image-video`, `keyframe-video` |

Mode aliases:

- `t2i` = `text-to-image`
- `i2i` = `image-to-image`
- `t2v` = `text-to-video`
- `i2v` = `image-to-video`
- `m2v` = `multi-image-video`
- `kfv` = `keyframe-video`

## Quick Start | 快速开始

### 1. Install | 安装

```bash
uv sync
```

Or with `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API keys | 配置 API Key

```bash
cp .env.local.example .env.local
```

Fill in only the keys you actually use. The scripts auto-load `.env.local` from the project root.

把你实际使用的 API Key 填入 `.env.local` 即可，脚本会自动加载该文件。

### 3. Run | 运行

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode t2i \
  --prompt "一只戴眼镜的小橘猫在图书馆看书，电影感，细节丰富"
```

## Examples | 示例

### Qwen text-to-image

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode t2i \
  --prompt "一只戴眼镜的小橘猫在图书馆看书，电影感，细节丰富"
```

### Gemini text-to-image

```bash
python3 scripts/generate_media.py \
  --provider gemini \
  --mode t2i \
  --prompt "A cozy reading corner with a cat and golden sunlight"
```

### Agens image-to-image

```bash
python3 scripts/generate_media.py \
  --provider agens \
  --mode i2i \
  --prompt "Transform this image into a rainy cyberpunk street scene while preserving the composition" \
  --image-url "https://example.com/input.png"
```

### Agens text-to-video

```bash
python3 scripts/generate_media.py \
  --provider agens \
  --mode t2v \
  --prompt "A cinematic close-up of an orange cat blinking in warm window light" \
  --num-frames 81 \
  --frame-rate 24 \
  --width 768 \
  --height 512 \
  --no-download
```

### Wuli image-to-image

```bash
python3 scripts/generate_media.py \
  --provider wuli \
  --mode i2i \
  --prompt "把这张商品图改成干净的奶油色电商布光，保留主体结构" \
  --image-url "https://example.com/input.png" \
  --aspect-ratio 1:1 \
  --resolution 2K
```

### Wuli keyframe video

```bash
python3 scripts/generate_media.py \
  --provider wuli \
  --mode kfv \
  --prompt "让镜头从首帧平滑推进到尾帧，保持电影感和真实光影" \
  --image-path ./frame-start.png \
  --image-path ./frame-end.png \
  --resolution 1080P \
  --aspect-ratio 16:9 \
  --video-seconds 5 \
  --no-download
```

### JSON output

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode t2i \
  --prompt "A cinematic portrait of an orange cat" \
  --json
```

## Sample Output | 输出示例

```text
$ python3 scripts/generate_media.py \
    --provider qwen \
    --mode t2i \
    --prompt "一只戴眼镜的小橘猫在图书馆看书，电影感，细节丰富"

🎨 正在调用 Qwen-Image API...
   模型: qwen-image-2.0-pro
   提示词: 一只戴眼镜的小橘猫在图书馆看书，电影感，细节丰富...
   尺寸: 2048*2048
   数量: 1
📥 正在下载 1 张图片...
   ✅ 保存到: ./generated_images/qwen_qwen-image-2.0-pro_20260621_170000_1.png
```

## Repository Layout | 仓库结构

- `scripts/`: CLI entrypoints and provider-specific generators
- `skill_runtime/`: shared runtime, HTTP client, env loading, key rotation, media download
- `references/`: API notes and prompt-writing guides
- `SKILL.md`: Codex skill metadata and usage instructions

## Notes | 说明

- Output files are saved to `./generated_images` by default
- Use `--output-dir` to change the output directory
- Gemini currently does not support `--no-download`
- Agens video generation is asynchronous and polled until completion or timeout
- Wuli tasks are asynchronous and polled until completion or timeout
- Wuli reference images/videos are auto-uploaded to Wuli OSS before task submission
- Wuli image references auto-fill `width` / `height` to avoid server-side validation errors
- `.env.local`, `.venv/`, `generated_images/`, and `__pycache__/` should not be committed

## Documentation | 参考文档

- [references/api_reference.md](references/api_reference.md)
- [references/prompt_guide.md](references/prompt_guide.md)
