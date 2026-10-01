"""
Autonomous Faceless YouTube Channel — Pipeline Orchestrator

Two input modes:
  1. Topic mode   — Claude generates the script from a topic string
  2. Direct mode  — you provide your own text + optional voice sample

Stage layout (dependency levels):
  Level 0:  ScriptWriter         — parses/generates script, title, thumbnail_prompt
  Level 1:  VoiceAgent           — clones your voice (OpenVoice) or falls back to TTS
            ImageAgent           — scene images (Diffusers / Pillow)
            ThumbnailAgent       — YouTube thumbnail (nano-banana / Gemini / Pillow)
  Level 2:  VideoAssembler       — assembles video (MoviePy / FFmpeg)
  Level 3:  UploadAgent          — uploads to YouTube (google-api-python-client)
            ArchiveAgent         — archives assets to Terabox (terabox-mcp)
"""

import asyncio
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Episode — shared state
# ---------------------------------------------------------------------------

@dataclass
class Episode:
    """Shared state passed through every pipeline stage."""

    # Required: at least one of topic or input_text must be set
    topic: str = ""
    input_text: str = ""          # provided text (skips Claude script generation)
    voice_sample: Path | None = None  # user's voice sample for cloning

    channel_name: str = "default"
    output_dir: Path = field(default_factory=lambda: Path("./output"))

    # Populated by stages
    script: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    voice_file: Path | None = None
    scene_images: list[Path] = field(default_factory=list)
    thumbnail_file: Path | None = None

    video_file: Path | None = None
    youtube_id: str = ""
    terabox_paths: dict[str, str] = field(default_factory=dict)

    errors: list[str] = field(default_factory=list)

    # Internal: set by ScriptWriter
    _thumbnail_prompt: str = ""

    def label(self) -> str:
        return self.title or self.topic or "episode"


# ---------------------------------------------------------------------------
# Stage base
# ---------------------------------------------------------------------------

class PipelineStage:
    name: str = "base"

    async def run(self, episode: Episode) -> Episode:
        raise NotImplementedError

    def log(self, msg: str):
        print(f"  [{self.name}] {msg}")


# ---------------------------------------------------------------------------
# Level 0 — Script Writer
# ---------------------------------------------------------------------------

class ScriptWriter(PipelineStage):
    name = "script-writer"

    async def run(self, episode: Episode) -> Episode:
        episode.output_dir.mkdir(parents=True, exist_ok=True)

        if episode.input_text.strip():
            # Direct mode: use provided text as-is
            self.log("Using provided text as script")
            await self._parse_provided(episode)
        else:
            # Topic mode: generate with Claude
            self.log(f"Generating script via Claude: {episode.topic}")
            await self._generate_from_topic(episode)

        # Save full script file
        script_path = episode.output_dir / "script.txt"
        script_path.write_text(
            f"TITLE: {episode.title}\n"
            f"DESCRIPTION: {episode.description}\n"
            f"TAGS: {','.join(episode.tags)}\n"
            f"THUMBNAIL_PROMPT: {episode._thumbnail_prompt}\n\n"
            f"SCRIPT:\n{episode.script}"
        )
        self.log(f"Script saved → {script_path}")
        return episode

    async def _parse_provided(self, episode: Episode):
        """Use the user's own text. Auto-generate title/tags if not embedded."""
        text = episode.input_text.strip()

        # Check if text already has structured headers
        if "TITLE:" in text:
            for line in text.splitlines():
                if line.startswith("TITLE:"):
                    episode.title = line[6:].strip()
                elif line.startswith("DESCRIPTION:"):
                    episode.description = line[12:].strip()
                elif line.startswith("TAGS:"):
                    episode.tags = [t.strip() for t in line[5:].split(",")]
                elif line.startswith("THUMBNAIL_PROMPT:"):
                    episode._thumbnail_prompt = line[17:].strip()
            if "SCRIPT:" in text:
                episode.script = text.split("SCRIPT:", 1)[1].strip()
            else:
                episode.script = text
        else:
            # Plain narration text — treat it all as the script
            episode.script = text
            # Try to derive title from first line
            first_line = text.splitlines()[0].strip()
            episode.title = first_line[:80] if first_line else (episode.topic or "My Video")

        # Fill defaults
        if not episode.description:
            episode.description = episode.title[:150]
        if not episode.tags:
            words = re.findall(r'\b[A-Za-z]{4,}\b', episode.title)
            episode.tags = list(dict.fromkeys(words))[:8]
        if not episode._thumbnail_prompt:
            episode._thumbnail_prompt = (
                f"Eye-catching YouTube thumbnail for: {episode.title}"
            )

        self.log(f"Title: {episode.title}")

    async def _generate_from_topic(self, episode: Episode):
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Write a 3-minute faceless YouTube narration script about: {episode.topic}\n\n"
                        "Format:\n"
                        "TITLE: <catchy title>\n"
                        "DESCRIPTION: <150-char YouTube description>\n"
                        "TAGS: tag1,tag2,tag3,tag4,tag5\n\n"
                        "SCRIPT:\n<narration — one paragraph per scene>\n\n"
                        "THUMBNAIL_PROMPT: <one sentence describing a compelling thumbnail image>"
                    ),
                }],
            )
            text = response.content[0].text
        except Exception as e:
            self.log(f"Claude unavailable ({e}) — using topic as script")
            text = (
                f"TITLE: {episode.topic} — Everything You Need To Know\n"
                f"DESCRIPTION: Discover the world of {episode.topic}.\n"
                f"TAGS: {episode.topic},facts,educational\n\n"
                f"SCRIPT:\nWelcome to this video about {episode.topic}.\n\n"
                f"Let's explore {episode.topic} together.\n\n"
                "Thank you for watching — like and subscribe!\n\n"
                f"THUMBNAIL_PROMPT: Cinematic illustration of {episode.topic}"
            )

        for line in text.splitlines():
            if line.startswith("TITLE:"):
                episode.title = line[6:].strip()
            elif line.startswith("DESCRIPTION:"):
                episode.description = line[12:].strip()
            elif line.startswith("TAGS:"):
                episode.tags = [t.strip() for t in line[5:].split(",")]
            elif line.startswith("THUMBNAIL_PROMPT:"):
                episode._thumbnail_prompt = line[17:].strip()

        if "SCRIPT:" in text:
            episode.script = text.split("SCRIPT:", 1)[1].split("THUMBNAIL_PROMPT:")[0].strip()

        self.log(f"Title: {episode.title}")


# ---------------------------------------------------------------------------
# Level 1 — Voice Agent (OpenVoice cloning + TTS)
# ---------------------------------------------------------------------------

class VoiceAgent(PipelineStage):
    name = "voice-agent"

    async def run(self, episode: Episode) -> Episode:
        out = episode.output_dir / "narration.wav"

        if episode.voice_sample and episode.voice_sample.exists():
            self.log(f"Cloning voice from: {episode.voice_sample.name}")
            success = await self._clone_voice(episode, out)
            if success:
                episode.voice_file = out
                return episode
            self.log("Voice cloning failed — falling back to TTS")

        self.log("Generating narration via TTS…")
        await self._tts_fallback(episode.script, out)
        episode.voice_file = out
        self.log(f"Voice → {out}")
        return episode

    async def _clone_voice(self, episode: Episode, out: Path) -> bool:
        """Clone the user's voice with OpenVoice and synthesise the narration."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parents[2] / "openvoice"))
            import torch
            from openvoice import se_extractor
            from openvoice.api import ToneColorConverter, BaseSpeakerTTS

            # Paths to OpenVoice checkpoints (download separately)
            ckpt_base = Path(__file__).parents[2] / "openvoice" / "checkpoints"
            base_speaker_ckpt = ckpt_base / "base_speakers" / "EN"
            converter_ckpt = ckpt_base / "converter"

            if not base_speaker_ckpt.exists():
                self.log("OpenVoice checkpoints not found at openvoice/checkpoints/")
                return False

            device = "cuda" if torch.cuda.is_available() else "cpu"

            # 1. Base TTS with a neutral voice
            base_tts = BaseSpeakerTTS(
                str(base_speaker_ckpt / "config.json"), device=device
            )
            base_tts.load_ckpt(str(base_speaker_ckpt / "checkpoint.pth"))
            tmp_out = out.parent / "narration_base.wav"
            base_tts.tts(episode.script, str(tmp_out), speaker="default",
                         language="English", speed=1.0)

            # 2. Extract tone colour from user's voice sample
            converter = ToneColorConverter(
                str(converter_ckpt / "config.json"), device=device
            )
            converter.load_ckpt(str(converter_ckpt / "checkpoint.pth"))
            target_se, _ = se_extractor.get_se(
                str(episode.voice_sample), converter, vad=True
            )
            source_se = torch.load(
                str(base_speaker_ckpt / "en_default_se.pth"), map_location=device
            )

            # 3. Convert tone colour → cloned voice
            converter.convert(
                audio_src_path=str(tmp_out),
                src_se=source_se,
                tgt_se=target_se,
                output_path=str(out),
                message="@OpenVoice",
            )
            self.log(f"Voice cloned → {out}")
            return True

        except ImportError as e:
            self.log(f"OpenVoice import error: {e}")
        except Exception as e:
            self.log(f"Voice cloning error: {e}")
        return False

    async def _tts_fallback(self, script: str, out: Path):
        """System TTS fallback (macOS say / espeak)."""
        for cmd in [
            ["say", "-o", str(out), "--data-format=LEF32@22050", script],
            ["espeak", "-w", str(out), script],
        ]:
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=120)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        self.log("No TTS available — writing script as text placeholder")
        out.write_text(script)


# ---------------------------------------------------------------------------
# Level 1 — Image Agent (Diffusers / Pillow)
# ---------------------------------------------------------------------------

class ImageAgent(PipelineStage):
    name = "image-agent"

    async def run(self, episode: Episode) -> Episode:
        self.log("Generating scene images…")
        scenes = [p for p in episode.script.split("\n\n") if p.strip()]
        images: list[Path] = []

        for i, scene in enumerate(scenes[:6]):
            img_path = episode.output_dir / f"scene_{i+1:02d}.png"
            prompt = f"Cinematic illustration: {scene[:120]}, 16:9, high quality"
            self.log(f"Scene {i+1}: {prompt[:55]}…")

            try:
                from diffusers import StableDiffusionPipeline
                import torch
                pipe = StableDiffusionPipeline.from_pretrained(
                    "runwayml/stable-diffusion-v1-5",
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                )
                image = pipe(prompt).images[0]
                image.save(img_path)
            except ImportError:
                try:
                    from PIL import Image, ImageDraw
                    img = Image.new("RGB", (1280, 720), color=(20, 20, 40))
                    draw = ImageDraw.Draw(img)
                    draw.text((40, 340), scene[:100], fill=(220, 220, 220))
                    img.save(img_path)
                except ImportError:
                    img_path.write_bytes(b"")

            images.append(img_path)

        episode.scene_images = images
        self.log(f"Generated {len(images)} scene images")
        return episode


# ---------------------------------------------------------------------------
# Level 1 — Thumbnail Agent (nano-banana / Gemini CLI / Pillow)
# ---------------------------------------------------------------------------

class ThumbnailAgent(PipelineStage):
    name = "thumbnail-agent"

    async def run(self, episode: Episode) -> Episode:
        self.log("Generating YouTube thumbnail…")
        out = episode.output_dir / "thumbnail.jpg"
        prompt = episode._thumbnail_prompt or f"YouTube thumbnail: {episode.title}"

        if await self._try_nanobanana(prompt, out):
            episode.thumbnail_file = out
            self.log(f"Thumbnail via Gemini → {out}")
            return episode

        self.log("Gemini unavailable — Pillow fallback")
        await self._pillow_thumbnail(episode.title, out)
        episode.thumbnail_file = out
        self.log(f"Thumbnail → {out}")
        return episode

    async def _try_nanobanana(self, prompt: str, out: Path) -> bool:
        """Try Gemini REST API image generation (no CLI extension required)."""
        key = os.getenv("NANOBANANA_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        if not key:
            return False
        enhanced = (
            f"{prompt}. YouTube thumbnail style: bold large text overlay, high contrast "
            "colours (red/yellow/white on dark), cinematic lighting, 16:9, professional."
        )
        # Try image-capable models in order of preference
        models = [
            "gemini-3.1-flash-image",
            "gemini-2.5-flash-image",
            "gemini-3.1-flash-image-preview",
        ]
        for model in models:
            if await self._gemini_image_rest(key, model, enhanced, out):
                return True
        return False

    async def _gemini_image_rest(self, key: str, model: str, prompt: str, out: Path) -> bool:
        import base64
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        try:
            async with __import__("httpx").AsyncClient(timeout=60) as client:
                r = await client.post(url, json=payload)
            d = r.json()
            if "error" in d:
                code = d["error"].get("code", 0)
                if code in (429, 400):  # quota / paid-plan required — skip silently
                    return False
                self.log(f"Gemini {model}: {d['error'].get('message','')[:80]}")
                return False
            for part in d.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    raw = base64.b64decode(part["inlineData"]["data"])
                    # Resize to exactly 1280×720 with Pillow
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                    img = img.resize((1280, 720), Image.LANCZOS)
                    img.save(out, "JPEG", quality=95)
                    return True
        except Exception as e:
            self.log(f"Gemini {model} error: {e}")
        return False

    async def _pillow_thumbnail(self, title: str, out: Path):
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (1280, 720))
            draw = ImageDraw.Draw(img)
            for y in range(720):
                r = int(20 + (y / 720) * 60)
                b = int(80 + (y / 720) * 120)
                draw.line([(0, y), (1280, y)], fill=(r, 10, b))
            words = title.split()
            lines, cur = [], ""
            for w in words:
                if len(cur) + len(w) + 1 > 28:
                    lines.append(cur.strip())
                    cur = w
                else:
                    cur += " " + w
            if cur:
                lines.append(cur.strip())
            y0 = 720 // 2 - len(lines) * 40
            for i, line in enumerate(lines):
                draw.text((640, y0 + i * 80), line, fill=(255, 255, 255), anchor="mm")
            img.save(out, "JPEG", quality=95)
        except ImportError:
            out.write_bytes(b"")


# ---------------------------------------------------------------------------
# Level 2 — Video Assembler (MoviePy / FFmpeg)
# ---------------------------------------------------------------------------

class VideoAssembler(PipelineStage):
    name = "video-assembler"

    async def run(self, episode: Episode) -> Episode:
        self.log("Assembling video…")
        out = episode.output_dir / "video.mp4"

        try:
            # MoviePy v2 — imports directly from moviepy (no .editor submodule)
            from moviepy import (
                AudioFileClip, ImageClip, ColorClip,
                CompositeVideoClip, concatenate_videoclips,
            )
            clips = []
            scene_dur = 10

            for img_path in episode.scene_images:
                if img_path.exists() and img_path.stat().st_size > 0:
                    clips.append(ImageClip(str(img_path)).with_duration(scene_dur))

            if not clips:
                clips = [ColorClip((1280, 720), color=(20, 10, 80), duration=30)]

            video = concatenate_videoclips(clips)

            if (episode.voice_file and episode.voice_file.exists()
                    and episode.voice_file.stat().st_size > 100):
                audio = AudioFileClip(str(episode.voice_file))
                trimmed = audio.subclipped(0, min(audio.duration, video.duration))
                video = video.with_audio(trimmed)

            video.write_videofile(str(out), fps=24, logger=None)
            self.log(f"Video → {out}")
        except ImportError:
            self.log("MoviePy not installed — placeholder")
            out.write_bytes(b"")

        episode.video_file = out
        return episode


# ---------------------------------------------------------------------------
# Level 3 — Upload Agent (YouTube API)
# ---------------------------------------------------------------------------

class UploadAgent(PipelineStage):
    name = "upload-agent"

    _SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    _API_SERVICE = "youtube"
    _API_VERSION = "v3"
    _CHUNK_SIZE = 256 * 1024  # 256 KB resumable upload chunk

    async def run(self, episode: Episode) -> Episode:
        self.log("Uploading to YouTube…")
        if not episode.video_file or not episode.video_file.exists():
            episode.errors.append("upload-agent: no video file")
            return episode

        secrets = os.getenv(
            "YOUTUBE_CLIENT_SECRETS_FILE",
            str(Path(__file__).parents[2] / "config" / "client_secrets.json"),
        )
        if not Path(secrets).exists():
            self.log(f"client_secrets.json not found at {secrets} — skipping upload")
            return episode

        try:
            youtube = await asyncio.get_event_loop().run_in_executor(
                None, self._build_service, secrets
            )
            video_id = await asyncio.get_event_loop().run_in_executor(
                None, self._upload_video, youtube, episode
            )
            episode.youtube_id = video_id
            self.log(f"Uploaded → https://youtu.be/{video_id}")

            if episode.thumbnail_file and episode.thumbnail_file.exists():
                await asyncio.get_event_loop().run_in_executor(
                    None, self._set_thumbnail, youtube, video_id, episode.thumbnail_file
                )
                self.log("Thumbnail set")

        except ImportError:
            self.log("google-api-python-client / google-auth-oauthlib not installed")
        except Exception as e:
            episode.errors.append(f"upload-agent: {e}")
            self.log(f"Upload error: {e}")

        return episode

    def _build_service(self, secrets_file: str):
        import pickle
        import googleapiclient.discovery
        from google_auth_oauthlib.flow import Flow
        from google.auth.transport.requests import Request

        token_path = Path(secrets_file).parent / "youtube_token.pkl"
        creds = None

        if token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if not sys.stdin.isatty():
                raise RuntimeError(
                    "YouTube OAuth2 requires an interactive terminal for first-time login.\n"
                    "Run the pipeline locally once to authorise, then copy "
                    f"config/youtube_token.pkl to this machine."
                )
            flow = Flow.from_client_secrets_file(
                secrets_file,
                scopes=self._SCOPES,
                redirect_uri="http://localhost:8080",
            )
            auth_url, _ = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )
            print(f"\n[upload-agent] Open this URL in your browser to authorise YouTube upload:")
            print(f"  {auth_url}\n")
            print("[upload-agent] After authorising, paste the full redirect URL (http://localhost:8080?code=...): ", end="", flush=True)
            redirect_response = input().strip()
            flow.fetch_token(authorization_response=redirect_response)
            creds = flow.credentials

            with open(token_path, "wb") as f:
                pickle.dump(creds, f)

        return googleapiclient.discovery.build(
            self._API_SERVICE, self._API_VERSION, credentials=creds
        )

    def _upload_video(self, youtube, episode: Episode) -> str:
        import googleapiclient.http

        body = {
            "snippet": {
                "title": episode.title[:100],
                "description": episode.description[:5000],
                "tags": episode.tags[:500],
                "categoryId": "22",  # People & Blogs — change as needed
            },
            "status": {
                "privacyStatus": "private",  # upload private first, review before publishing
                "selfDeclaredMadeForKids": False,
            },
        }

        media = googleapiclient.http.MediaFileUpload(
            str(episode.video_file),
            mimetype="video/mp4",
            resumable=True,
            chunksize=self._CHUNK_SIZE,
        )

        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"  [upload-agent] Uploading… {pct}%", end="\r", flush=True)

        print()
        return response["id"]

    def _set_thumbnail(self, youtube, video_id: str, thumbnail: Path):
        import googleapiclient.http

        youtube.thumbnails().set(
            videoId=video_id,
            media_body=googleapiclient.http.MediaFileUpload(
                str(thumbnail), mimetype="image/jpeg"
            ),
        ).execute()


# ---------------------------------------------------------------------------
# Level 3 — Archive Agent (Terabox)
# ---------------------------------------------------------------------------

class ArchiveAgent(PipelineStage):
    name = "archive-agent"

    async def run(self, episode: Episode) -> Episode:
        self.log("Archiving to Terabox…")
        cookie = os.getenv("TERABOX_COOKIE", "")
        if not cookie:
            self.log("TERABOX_COOKIE not set — skipping")
            return episode

        import sys
        sys.path.insert(0, str(Path(__file__).parents[1] / "mcp" / "terabox-mcp"))
        from client import TeraboxClient

        assets = {
            "video": episode.video_file,
            "thumbnail": episode.thumbnail_file,
            "audio": episode.voice_file,
            "script": episode.output_dir / "script.txt",
        }
        async with TeraboxClient(cookie=cookie) as tb:
            for ctype, path in assets.items():
                if path and path.exists() and path.stat().st_size > 0:
                    remote = f"/youtube-channel/{episode.channel_name}/{ctype}/{path.name}"
                    try:
                        await tb.create_folder(remote.rsplit("/", 1)[0])
                    except Exception:
                        pass
                    await tb.upload_file(str(path), remote)
                    episode.terabox_paths[ctype] = remote
                    self.log(f"Archived {ctype} → {remote}")

        return episode


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------

class YouTubePipeline:
    """
    Runs the full pipeline.

    Direct mode  — provide input_text (+ optional voice_sample)
    Topic mode   — provide topic (Claude generates the script)
    """

    async def run(
        self,
        topic: str = "",
        input_text: str = "",
        voice_sample: str | Path | None = None,
        channel_name: str = "default",
        output_dir: str = "./output",
    ) -> Episode:

        if not topic and not input_text:
            raise ValueError("Provide either --topic or --text")

        episode = Episode(
            topic=topic,
            input_text=input_text,
            voice_sample=Path(voice_sample) if voice_sample else None,
            channel_name=channel_name,
            output_dir=Path(output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S"),
        )
        episode.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'═'*58}")
        mode = "direct text" if input_text else f"topic: {topic}"
        voice_info = f" + voice clone ({Path(voice_sample).name})" if voice_sample else ""
        print(f"  YouTube Pipeline — {mode}{voice_info}")
        print(f"{'═'*58}\n")

        # Level 0
        episode = await ScriptWriter().run(episode)

        # Level 1 — parallel
        episode = await self._parallel(
            episode, [VoiceAgent(), ImageAgent(), ThumbnailAgent()]
        )

        # Level 2
        episode = await VideoAssembler().run(episode)

        # Level 3 — parallel
        episode = await self._parallel(episode, [UploadAgent(), ArchiveAgent()])

        self._summary(episode)
        return episode

    async def _parallel(self, episode: Episode, stages: list[PipelineStage]) -> Episode:
        results = await asyncio.gather(
            *[stage.run(episode) for stage in stages],
            return_exceptions=True,
        )
        for stage, result in zip(stages, results):
            if isinstance(result, Exception):
                episode.errors.append(f"{stage.name}: {result}")
                print(f"  [{stage.name}] ERROR: {result}")
            else:
                for k, v in result.__dict__.items():
                    if v is not None and v != [] and v != {}:
                        setattr(episode, k, v)
        return episode

    def _summary(self, episode: Episode):
        ok = "✓"
        print(f"\n{'═'*58}")
        print("  Done")
        print(f"{'═'*58}")
        print(f"  {ok} Title:     {episode.title or episode.topic}")
        print(f"  {ok} Voice:     {episode.voice_file}")
        print(f"  {ok} Thumbnail: {episode.thumbnail_file}")
        print(f"  {ok} Video:     {episode.video_file}")
        print(f"  {'✗' if not episode.youtube_id else ok} YouTube:   {episode.youtube_id or 'not uploaded'}")
        print(f"  {ok} Terabox:   {list(episode.terabox_paths.keys()) or 'not archived'}")
        if episode.errors:
            print(f"  ! Errors:    {episode.errors}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Autonomous YouTube channel pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Topic mode (Claude writes the script):
  python youtube_pipeline.py --topic "10 Facts About Black Holes"

  # Direct mode (your own text, no LLM needed):
  python youtube_pipeline.py --text my_script.txt

  # Direct mode + voice cloning (your voice, your text):
  python youtube_pipeline.py --text my_script.txt --voice my_voice.wav

  # Full with channel name:
  python youtube_pipeline.py --text script.txt --voice voice.wav --channel mychannel
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", help="Topic for Claude to write a script about")
    group.add_argument("--text", help="Path to your own narration text file (or inline text)")
    parser.add_argument("--voice", help="Path to your voice sample (.wav/.mp3) for cloning")
    parser.add_argument("--channel", default="default", help="Channel name (Terabox folder)")
    parser.add_argument("--output", default="./output", help="Output directory")
    args = parser.parse_args()

    # --text can be a file path or inline text
    input_text = ""
    if args.text:
        p = Path(args.text)
        input_text = p.read_text() if p.exists() else args.text

    asyncio.run(YouTubePipeline().run(
        topic=args.topic or "",
        input_text=input_text,
        voice_sample=args.voice,
        channel_name=args.channel,
        output_dir=args.output,
    ))
