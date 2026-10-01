import json
import os
import sys
import time
from pathlib import Path

import edge_tts
import requests


ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"


if ENV_PATH.exists():
    for line in ENV_PATH.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        line = line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip()
            .strip('"')
            .strip("'")
        )


API_KEY = os.getenv("SHOTSTACK_API_KEY")
API_BASE = os.getenv("SHOTSTACK_API_BASE")

VOICE = os.getenv(
    "REEL_TTS_VOICE",
    "de-DE-ConradNeural",
)

VOICE_RATE = os.getenv(
    "REEL_TTS_RATE",
    "+4%",
)

VOICE_PITCH = os.getenv(
    "REEL_TTS_PITCH",
    "-2Hz",
)


if not API_KEY:
    raise RuntimeError(
        "SHOTSTACK_API_KEY fehlt."
    )

if not API_BASE:
    raise RuntimeError(
        "SHOTSTACK_API_BASE fehlt."
    )


def shotstack_version():

    version = (
        API_BASE.rstrip("/")
        .split("/")[-1]
    )

    if version not in {
        "stage",
        "v1",
    }:
        raise RuntimeError(
            "SHOTSTACK_API_BASE muss "
            "auf /stage oder /v1 enden."
        )

    return version


def create_voice(
    text: str,
    output: Path,
):

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    communicator = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=VOICE_RATE,
        pitch=VOICE_PITCH,
        boundary="WordBoundary",
    )

    last_end = 0.0

    with output.open("wb") as audio:

        for chunk in communicator.stream_sync():

            if chunk["type"] == "audio":

                audio.write(
                    chunk["data"]
                )

            elif (
                chunk["type"]
                == "WordBoundary"
            ):

                end = (
                    chunk["offset"]
                    + chunk["duration"]
                ) / 10_000_000

                last_end = max(
                    last_end,
                    end,
                )

    if output.stat().st_size == 0:
        raise RuntimeError(
            "TTS hat keine Audiodaten erzeugt."
        )

    return max(
        last_end,
        0.1,
    )


def upload_to_shotstack(
    path: Path,
):

    version = shotstack_version()

    headers = {
        "x-api-key": API_KEY,
        "Accept": "application/json",
    }

    response = requests.post(
        (
            "https://api.shotstack.io/"
            f"ingest/{version}/upload"
        ),
        headers=headers,
        json={
            "filename": path.name,
        },
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    upload_url = (
        data["data"]
        ["attributes"]
        ["url"]
    )

    source_id = (
        data["data"]["id"]
    )

    with path.open("rb") as media:

        upload = requests.put(
            upload_url,
            data=media,
            timeout=600,
        )

    upload.raise_for_status()

    for _ in range(120):

        status_response = requests.get(
            (
                "https://api.shotstack.io/"
                f"ingest/{version}/sources/"
                f"{source_id}"
            ),
            headers=headers,
            timeout=60,
        )

        status_response.raise_for_status()

        attributes = (
            status_response
            .json()
            ["data"]
            ["attributes"]
        )

        status = attributes["status"]

        if status == "ready":

            return attributes["source"]

        if status == "failed":

            raise RuntimeError(
                "Shotstack konnte das "
                "Voice-over nicht verarbeiten."
            )

        time.sleep(2)

    raise TimeoutError(
        "Voice-over Upload Timeout."
    )


def get_voice_text(reel):

    explicit = (
        reel.get("voiceover_text")
        or reel.get("narration")
        or reel.get("voiceover")
    )

    if explicit:

        return str(
            explicit
        ).strip()

    parts = []

    for key in (
        "hook",
        "caption",
        "cta",
    ):

        value = str(
            reel.get(key)
            or ""
        ).strip()

        if (
            value
            and value not in parts
        ):

            parts.append(value)

    text = ". ".join(parts)

    if not text:

        raise RuntimeError(
            "Kein Sprechertext gefunden."
        )

    return text


def render_job(
    job_id: str,
):

    job_file = (
        ROOT
        / "core"
        / "jobs"
        / f"{job_id}.json"
    )

    plan_file = (
        ROOT
        / "exports"
        / job_id
        / "reel-plan.json"
    )

    output_dir = (
        ROOT
        / "exports"
        / job_id
    )

    if not job_file.exists():

        raise FileNotFoundError(
            f"Job fehlt: {job_file}"
        )

    if not plan_file.exists():

        raise FileNotFoundError(
            f"Reel-Plan fehlt: {plan_file}"
        )

    job = json.loads(
        job_file.read_text(
            encoding="utf-8-sig"
        )
    )

    plan = json.loads(
        plan_file.read_text(
            encoding="utf-8-sig"
        )
    )

    video_url = job.get(
        "input_url"
    )

    if not video_url:

        raise RuntimeError(
            "Reels-Job braucht input_url."
        )

    reel = plan["reel"]

    start = float(
        reel["start"]
    )

    end = float(
        reel["end"]
    )

    duration = (
        end - start
    )

    if duration <= 0:

        raise RuntimeError(
            "Ungültige Reel-Dauer."
        )


    # ==========================================
    # NATÜRLICHE MÄNNLICHE STIMME
    # ==========================================

    voice_text = get_voice_text(
        reel
    )

    voice_file = (
        output_dir
        / "voiceover.mp3"
    )

    print(
        f"TTS_VOICE={VOICE}"
    )

    print(
        "TTS_GENERATING"
    )

    voice_duration = create_voice(
        voice_text,
        voice_file,
    )

    if (
        voice_duration
        > duration + 0.4
    ):

        print(
            "WARNUNG: Voice-over ist "
            "länger als der Videoschnitt."
        )


    print(
        "TTS_UPLOAD"
    )

    voice_url = (
        upload_to_shotstack(
            voice_file
        )
    )


    audio_length = min(
        voice_duration + 0.2,
        duration,
    )

    hook = str(
        reel.get("hook")
        or reel.get("title")
        or ""
    ).strip()


    # ==========================================
    # SCHÖNE SYNCHRONISIERTE UNTERTITEL
    # ==========================================

    caption_clip = {

        "asset": {

            "type": "rich-caption",

            # Untertitel werden direkt aus
            # derselben Stimme erzeugt.
            "src": "alias://narrator",

            "font": {
                "family": "Montserrat",
                "size": 58,
                "weight": 800,
                "color": "#FFFFFF",
                "opacity": 1,
            },

            "stroke": {
                "width": 4,
                "color": "#000000",
                "opacity": 1,
            },

            "shadow": {
                "offsetX": 0,
                "offsetY": 4,
                "blur": 8,
                "color": "#000000",
                "opacity": 0.90,
            },

            "background": {
                "color": "#000000",
                "opacity": 0.34,
                "borderRadius": 24,
                "wrap": True,
            },

            "padding": 18,

            "align": {
                "horizontal": "center",
                "vertical": "bottom",
            },

            # Gerade gesprochenes Wort
            # wird gelb hervorgehoben.
            "active": {

                "font": {
                    "color": "#FFD400",
                    "size": 66,
                    "weight": 900,
                },

                "stroke": {
                    "width": 4,
                    "color": "#000000",
                    "opacity": 1,
                },
            },

            "animation": {
                "style": "highlight",
            },
        },

        "start": 0,
        "length": audio_length,

        # etwas oberhalb des Instagram-
        # Bedienbereichs
        "offset": {
            "y": 0.08,
        },
    }


    tracks = [
        {
            "clips": [
                caption_clip
            ]
        }
    ]


    # ==========================================
    # HOOK / TITEL
    # ==========================================

    if hook:

        tracks.append({

            "clips": [{

                "asset": {

                    "type": "rich-text",

                    "text": hook.upper(),

                    "font": {
                        "family": "Montserrat",
                        "size": 72,
                        "weight": 900,
                        "color": "#FFFFFF",
                    },

                    "stroke": {
                        "width": 4,
                        "color": "#000000",
                        "opacity": 1,
                    },

                    "shadow": {
                        "offsetX": 0,
                        "offsetY": 5,
                        "blur": 10,
                        "color": "#000000",
                        "opacity": 0.90,
                    },

                    "background": {
                        "color": "#000000",
                        "opacity": 0.42,
                        "borderRadius": 28,
                        "wrap": True,
                    },

                    "padding": 20,

                    "align": {
                        "horizontal": "center",
                        "vertical": "middle",
                    },

                    "animation": {
                        "preset": "shift",
                        "duration": 0.45,
                        "style": "word",
                        "direction": "up",
                    },
                },

                "start": 0,

                "length": min(
                    2.8,
                    duration,
                ),

                "width": 940,
                "height": 250,

                "position": "top",

                "offset": {
                    "y": -0.07,
                },
            }]
        })


    # ==========================================
    # SPRECHER-AUDIO
    # ==========================================

    tracks.append({

        "clips": [{

            "alias": "narrator",

            "asset": {
                "type": "audio",
                "src": voice_url,
                "volume": 1,
            },

            "start": 0,
            "length": audio_length,
        }]
    })


    # ==========================================
    # ORIGINALVIDEO
    # ==========================================

    tracks.append({

        "clips": [{

            "asset": {
                "type": "video",
                "src": video_url,
                "trim": start,

                # Original-/Game-Sound leise
                # unter dem Sprecher.
                "volume": 0.18,
            },

            "start": 0,
            "length": duration,
            "fit": "crop",
        }]
    })


    payload = {

        "timeline": {

            "background": "#000000",

            "tracks": tracks,
        },

        "output": {

            "format": "mp4",

            "size": {
                "width": 1080,
                "height": 1920,
            },
        },
    }


    response = requests.post(

        f"{API_BASE.rstrip('/')}/render",

        headers={
            "x-api-key": API_KEY,
            "Content-Type":
                "application/json",
            "Accept":
                "application/json",
        },

        json=payload,

        timeout=120,
    )


    if not response.ok:

        print(
            "SHOTSTACK_STATUS=",
            response.status_code,
        )

        print(
            "SHOTSTACK_RESPONSE=",
            response.text,
        )

        response.raise_for_status()


    data = response.json()

    render_id = (
        data["response"]["id"]
    )


    result_file = (
        output_dir
        / "shotstack-job.json"
    )


    result_file.write_text(

        json.dumps(

            {
                "render_id":
                    render_id,

                "source_video":
                    video_url,

                "voice":
                    VOICE,

                "voiceover_text":
                    voice_text,

                "voiceover_file":
                    str(voice_file),

                "voiceover_url":
                    voice_url,

                "voice_duration":
                    voice_duration,

                "payload":
                    payload,
            },

            ensure_ascii=False,

            indent=2,
        ),

        encoding="utf-8",
    )


    return (
        render_id,
        result_file,
    )


if __name__ == "__main__":

    if len(sys.argv) != 2:

        print(
            "SHOTSTACK_REEL_V2_READY"
        )

        print(
            "USAGE: python "
            "render_reel_v2.py "
            "JOB-XXXXXXXX"
        )

        sys.exit(0)


    render_id, result_file = (
        render_job(
            sys.argv[1]
        )
    )


    print(
        "REEL_RENDER_QUEUED"
    )

    print(
        f"RENDER_ID={render_id}"
    )

    print(
        f"OUTPUT={result_file}"
    )
