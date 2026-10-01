#!/usr/bin/env python3
"""
Autonomous Faceless YouTube Channel — single entry point.

Usage
-----
# Your text + your voice → full video, auto-archived:
  python src/run.py --text my_script.txt --voice my_voice.wav

# Just text (system TTS, no voice cloning):
  python src/run.py --text my_script.txt

# Let Claude write the script for you:
  python src/run.py --topic "10 Facts About Black Holes"

# Override channel name and output folder:
  python src/run.py --text script.txt --voice voice.wav --channel mychannel --output ./out

Environment variables (optional — stages degrade gracefully when missing)
--------------------------------------------------------------------------
  ANTHROPIC_API_KEY            Claude script generation
  NANOBANANA_GEMINI_API_KEY    Gemini thumbnail via nano-banana
  TERABOX_COOKIE               Archive assets to Terabox
  YOUTUBE_CLIENT_SECRETS_FILE  Upload video to YouTube
"""

import sys
import os
from pathlib import Path

# Make src/ importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

# Load .env from repo root (if present) — never overrides already-set env vars
def _load_env():
    env_path = Path(__file__).parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

_load_env()

from pipeline.youtube_pipeline import YouTubePipeline
import asyncio
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Autonomous YouTube channel pipeline — text + voice → video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--text", metavar="FILE_OR_TEXT",
        help="Your narration text: path to a .txt file OR inline text string",
    )
    mode.add_argument(
        "--topic", metavar="TOPIC",
        help="Topic for Claude to write the script (requires ANTHROPIC_API_KEY)",
    )

    parser.add_argument(
        "--voice", metavar="VOICE_SAMPLE",
        help="Path to your voice sample (.wav / .mp3) for voice cloning via OpenVoice",
    )
    parser.add_argument("--channel", default="default",
                        help="Channel name — used as subfolder in Terabox (default: default)")
    parser.add_argument("--output", default="./output",
                        help="Local output directory (default: ./output)")

    args = parser.parse_args()

    # Resolve --text: file path or inline string
    input_text = ""
    if args.text:
        p = Path(args.text)
        if p.exists():
            input_text = p.read_text(encoding="utf-8")
            print(f"[run] Text loaded from {p} ({len(input_text)} chars)")
        else:
            input_text = args.text
            print(f"[run] Using inline text ({len(input_text)} chars)")

    # Resolve --voice
    voice_sample = None
    if args.voice:
        voice_sample = Path(args.voice)
        if not voice_sample.exists():
            print(f"[run] WARNING: voice sample not found: {voice_sample}")
            voice_sample = None
        else:
            print(f"[run] Voice sample: {voice_sample}")

    # Run
    asyncio.run(YouTubePipeline().run(
        topic=args.topic or "",
        input_text=input_text,
        voice_sample=voice_sample,
        channel_name=args.channel,
        output_dir=args.output,
    ))


if __name__ == "__main__":
    main()
