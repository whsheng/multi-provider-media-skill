# multi-provider-media-skill

`multi-provider-media-skill` is a Codex skill and CLI toolkit for multi-provider AI image and video generation. It unifies Qwen, Gemini Imagen, and Agens-AI behind one command interface, with API key rotation, local `.env.local` loading, async task polling, and downloadable outputs.

`multi-provider-media-skill` 是一个面向 Codex/Agent 工作流的多模型图片与视频生成 Skill 和命令行工具。它把 Qwen、Gemini Imagen 和 Agens-AI 统一到一个调用入口下，并内置 API Key 轮询、`.env.local` 自动加载、异步任务轮询和本地结果下载能力。

## Features | 功能

- Unified CLI entry: `scripts/generate_media.py`
- Providers: `Qwen`, `Gemini Imagen`, `Agens-AI`
- Modes: text-to-image, image-to-image, text-to-video, image-to-video, multi-image video, keyframe video
- Built-in multi-key rotation and local output download
- Auto-loads `.env.local` from the project root

## Quick Start | 快速开始

### Install | 安装

```bash
uv sync
```

Or use `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure API keys | 配置 API Key

```bash
cp .env.local.example .env.local
```

Then fill in the keys you actually use in `.env.local`.

然后把你实际使用的 API Key 填进 `.env.local`。

### Run | 运行

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode t2i \
  --prompt "一只戴眼镜的小橘猫在图书馆看书，电影感，细节丰富"
```

## Providers And Modes | 支持的服务与模式

| Provider | Default model | Modes |
|---|---|---|
| Qwen | `qwen-image-2.0-pro` | `text-to-image` |
| Gemini Imagen | `imagen-3.0-generate-002` | `text-to-image` |
| Agens-AI | `agnes-image-2.1-flash` / `agnes-video-v2.0` | `text-to-image`, `image-to-image`, `text-to-video`, `image-to-video`, `multi-image-video`, `keyframe-video` |

Mode aliases:

- `t2i` = `text-to-image`
- `i2i` = `image-to-image`
- `t2v` = `text-to-video`
- `i2v` = `image-to-video`
- `m2v` = `multi-image-video`
- `kfv` = `keyframe-video`

## Examples | 示例

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

### JSON output

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode t2i \
  --prompt "A cinematic portrait of an orange cat" \
  --json
```

## Repository Layout | 目录结构

- `scripts/`: CLI entrypoints and provider-specific generators
- `skill_runtime/`: shared runtime, HTTP client, env loading, key rotation, media download
- `references/`: API notes and prompt-writing guides
- `SKILL.md`: Codex skill definition

## Notes | 说明

- Output files are saved to `./generated_images` by default
- Use `--output-dir` to change the output directory
- Gemini currently does not support `--no-download`
- Agens video generation is asynchronous and polled until completion or timeout
- `.env.local`, `.venv/`, `generated_images/`, and `__pycache__/` should not be committed

## References | 参考资料

- [references/api_reference.md](references/api_reference.md)
- [references/prompt_guide.md](references/prompt_guide.md)
