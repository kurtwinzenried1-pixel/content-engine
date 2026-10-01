# Create Video

Run the complete autonomous YouTube channel pipeline with your own text and voice.

## Quickstart

```bash
# Your text + your voice → full video
python src/run.py --text my_script.txt --voice my_voice.wav

# Just text (system TTS, no voice cloning)
python src/run.py --text my_script.txt

# Let Claude write the script
python src/run.py --topic "10 Facts About Black Holes"
```

## What happens automatically

```
  Your text ──────────────────────────────────────────────────────────┐
  Your voice ─────────────────────────────────────────────────────────┤
                                                                       ▼
  [ScriptWriter]  Parses your text → title, tags, thumbnail_prompt
        │
        ├──► [VoiceAgent]     Clones YOUR voice (OpenVoice) + synthesises narration
        ├──► [ImageAgent]     Generates scene images (Diffusers / Pillow)
        └──► [ThumbnailAgent] Creates YouTube thumbnail (nano-banana / Pillow)
                                    ▼
        [VideoAssembler]  Stitches images + cloned voice → video.mp4 (MoviePy)
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
         [UploadAgent]                    [ArchiveAgent]
         Uploads to YouTube               Saves everything to Terabox
```

## Output

```
output/{timestamp}/
  script.txt        ← your text + metadata
  narration.wav     ← your voice, cloned narration
  scene_01.png      ← scene images
  scene_02.png
  ...
  thumbnail.jpg     ← YouTube thumbnail (nano-banana)
  video.mp4         ← final video
```

## Text format (optional headers)

Your text file can be plain narration, or include optional headers:

```
TITLE: My Amazing Video Title
DESCRIPTION: Short YouTube description here
TAGS: tag1, tag2, tag3
THUMBNAIL_PROMPT: Cinematic space scene with glowing planets

SCRIPT:
Welcome to this video...

In this section we explore...

Thank you for watching!
```

If you omit the headers, the pipeline auto-generates them from your text.

## Voice cloning

Provide a clean voice sample (3–30 seconds, WAV or MP3) of you speaking.
OpenVoice extracts your tone and applies it to the narration.

```bash
# Record a quick sample:
# macOS:  say -o my_voice.aiff "Hello, this is my voice sample for cloning"
#         ffmpeg -i my_voice.aiff my_voice.wav
# Linux:  arecord -d 10 -f cd my_voice.wav
```

## Required environment variables

| Variable | Stage | Effect if missing |
|----------|-------|-------------------|
| `ANTHROPIC_API_KEY` | ScriptWriter | Skips Claude — uses your text as-is |
| `NANOBANANA_GEMINI_API_KEY` | ThumbnailAgent | Falls back to Pillow thumbnail |
| `TERABOX_COOKIE` | ArchiveAgent | Skips cloud archive |
| `YOUTUBE_CLIENT_SECRETS_FILE` | UploadAgent | Skips YouTube upload |

All stages degrade gracefully — the pipeline always runs to completion.

## Install dependencies

```bash
pip install anthropic moviepy pillow diffusers torch httpx mcp
npm install -g @google/gemini-cli
gemini extensions install https://github.com/gemini-cli-extensions/nanobanana
```
