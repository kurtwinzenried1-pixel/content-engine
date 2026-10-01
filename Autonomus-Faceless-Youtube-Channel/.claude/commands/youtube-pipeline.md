# YouTube Pipeline

Run the full autonomous faceless YouTube channel pipeline for a given topic.

## Usage

```
/youtube-pipeline <topic> [--channel <name>] [--output <dir>]
```

## What it does

Produces a complete YouTube episode end-to-end:

1. **ScriptWriter** — Claude generates narration script, title, tags, thumbnail prompt
2. **VoiceAgent** — OpenVoice/TTS converts script to narration audio
3. **ImageAgent** — Diffusers generates one scene image per paragraph *(parallel)*
4. **ThumbnailAgent** — nano-banana (Gemini CLI) generates YouTube thumbnail *(parallel)*
5. **VideoAssembler** — MoviePy assembles images + audio into .mp4
6. **UploadAgent** — uploads video + thumbnail to YouTube
7. **ArchiveAgent** — archives all assets to Terabox

## Quick start

```bash
python src/pipeline/youtube_pipeline.py "10 Facts About Black Holes" \
  --channel my-channel \
  --output ./output
```

## Required env vars

```bash
export ANTHROPIC_API_KEY="..."              # Claude (script)
export NANOBANANA_GEMINI_API_KEY="..."      # Gemini (thumbnail)
export TERABOX_COOKIE="..."                 # Terabox (archive)
export YOUTUBE_CLIENT_SECRETS_FILE="..."    # YouTube (upload)
```

## Thumbnail integration

The **ThumbnailAgent** runs at **Level 1** (in parallel with voice + image generation).
It uses the `nano-banana` skill (`.claude/commands/nano-banana.md`) backed by Gemini CLI.

```
ScriptWriter → [VoiceAgent | ImageAgent | ThumbnailAgent] → VideoAssembler → [UploadAgent | ArchiveAgent]
```

The thumbnail prompt is extracted from the script by Claude:
> "Eye-catching cinematic illustration of black holes with bold text overlay"

This prompt is automatically enhanced for YouTube style before being sent to Gemini.

## Output structure

```
./output/{timestamp}/
  script.txt          ← full script with title/tags/prompt
  narration.wav       ← TTS audio
  scene_01.png        ← scene images
  scene_02.png
  ...
  thumbnail.jpg       ← 1280×720 YouTube thumbnail ◄ nano-banana
  video.mp4           ← final rendered video
```

## Agents involved

See `.claude/agents/youtube/` for all agent definitions:
- `youtube-swarm.md` — swarm coordinator
- `thumbnail-agent.md` — thumbnail specialist (nano-banana)
