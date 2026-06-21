---
name: multi-provider-media-skill
description: This skill provides image and video generation capabilities using
  Qwen (通义千问), Gemini Imagen, Agens-AI, and Wuli APIs. Use this skill when
  users request text-to-image, image-to-image, text-to-video, image-to-video, or
  similar media generation tasks, such as "生成一张图片"、"画一张图"、"生成一个视频"、"create an
  image", "generate a picture", or when they provide prompts or image URLs they
  want transformed into media.
disable: false
---

统一入口脚本:

- `scripts/generate_media.py`

本地 API Key 管理:

- 推荐使用项目根目录的 `.env.local`
- 脚本会自动加载 `.env.local`
- 示例模板见 `.env.local.example`
- `.env.local` 已加入 `.gitignore`

核心调用方式:

- `--provider qwen|gemini|agens|wuli`
- `--mode text-to-image|image-to-image|text-to-video|image-to-video|multi-image-video|keyframe-video`

示例:

```bash
python3 scripts/generate_media.py \
  --provider agens \
  --mode text-to-video \
  --prompt "A cinematic close-up of an orange cat blinking in warm window light" \
  --num-frames 81 \
  --frame-rate 24 \
  --width 768 \
  --height 512 \
  --no-download
```

```bash
python3 scripts/generate_media.py \
  --provider qwen \
  --mode text-to-image \
  --prompt "一只戴眼镜的小橘猫在图书馆看书，电影感，细节丰富"
```
