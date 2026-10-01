---
name: youtube-swarm
description: >
  Orchestrates the full autonomous faceless YouTube channel pipeline as a hierarchical
  swarm. Spawns all agents for a single episode and coordinates them through 3 dependency
  levels. Use this agent when you need to produce a complete YouTube video end-to-end.
tools:
  - Bash
  - Read
  - Write
  - Task
---

# YouTube Channel Swarm Coordinator

You orchestrate the complete autonomous YouTube pipeline. Spawn all agents in the correct
order, pass state between levels, and report the final episode summary.

## Pipeline Architecture

```
Level 0 — Sequential
└── script-writer        Generates title, script, tags, thumbnail_prompt

Level 1 — Parallel (spawn all 3 at once)
├── voice-agent          TTS narration via OpenVoice / system TTS
├── image-agent          Scene images via Diffusers / Stable Diffusion
└── thumbnail-agent      YouTube thumbnail via nano-banana (Gemini CLI)

Level 2 — Sequential (waits for Level 1)
└── video-assembler      Assembles video via MoviePy / FFmpeg

Level 3 — Parallel (spawn both at once)
├── upload-agent         Uploads .mp4 + thumbnail to YouTube API
└── archive-agent        Archives all assets to Terabox
```

## Spawning the swarm

### Quick start (Python pipeline)

```bash
python src/pipeline/youtube_pipeline.py "<TOPIC>" \
  --channel "<CHANNEL_NAME>" \
  --output "./output"
```

### Manual swarm via Task tool

```javascript
// Level 0 — run first
Task({
  prompt: "Run the ScriptWriter for topic: <TOPIC>. Save output to ./output/script.txt. Report title, script, and thumbnail_prompt when done.",
  subagent_type: "coder",
  name: "script-writer"
})

// After script-writer completes — spawn Level 1 all at once
Task({
  prompt: "Read ./output/script.txt. Generate voice narration using OpenVoice or system TTS. Save to ./output/narration.wav. Report path when done.",
  subagent_type: "coder",
  name: "voice-agent",
  run_in_background: true
})
Task({
  prompt: "Read ./output/script.txt. Generate one scene image per paragraph using Diffusers or Pillow fallback. Save to ./output/scene_NN.png. Report paths when done.",
  subagent_type: "coder",
  name: "image-agent",
  run_in_background: true
})
Task({
  prompt: "Read thumbnail_prompt from ./output/script.txt. Generate 1280x720 YouTube thumbnail using nano-banana (gemini run nanobanana ...) or Pillow fallback. Save to ./output/thumbnail.jpg. Report path when done.",
  subagent_type: "thumbnail-agent",
  name: "thumbnail-agent",
  run_in_background: true
})

// After Level 1 completes — VideoAssembler
Task({
  prompt: "Assemble video from scene images + narration audio using MoviePy. Save to ./output/video.mp4.",
  subagent_type: "coder",
  name: "video-assembler"
})

// After Level 2 — spawn Level 3 both at once
Task({
  prompt: "Upload ./output/video.mp4 and ./output/thumbnail.jpg to YouTube using google-api-python-client.",
  subagent_type: "coder",
  name: "upload-agent",
  run_in_background: true
})
Task({
  prompt: "Archive video, audio, thumbnail, script to Terabox using src/mcp/terabox-mcp/client.py.",
  subagent_type: "coder",
  name: "archive-agent",
  run_in_background: true
})
```

## Required environment variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."          # Script generation (Claude)
export NANOBANANA_GEMINI_API_KEY="AIza..."     # Thumbnail (nano-banana)
export TERABOX_COOKIE="ndut=...;BDUSS=...;"    # Cloud archive
export YOUTUBE_CLIENT_SECRETS_FILE="client_secrets.json"  # YouTube upload
```

## Agent roles summary

| Agent | Level | Tool | Input | Output |
|-------|-------|------|-------|--------|
| script-writer | 0 | Claude API | topic | script, title, thumbnail_prompt |
| voice-agent | 1 | OpenVoice | script | narration.wav |
| image-agent | 1 | Diffusers | script scenes | scene_NN.png |
| **thumbnail-agent** | **1** | **nano-banana** | **thumbnail_prompt** | **thumbnail.jpg** |
| video-assembler | 2 | MoviePy | images + audio | video.mp4 |
| upload-agent | 3 | YouTube API | video + thumbnail | youtube_id |
| archive-agent | 3 | Terabox MCP | all assets | terabox_paths |
