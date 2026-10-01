import json
import os
import sys
from pathlib import Path

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
        )


API_KEY = os.getenv("SHOTSTACK_API_KEY")
API_BASE = os.getenv("SHOTSTACK_API_BASE")

if not API_KEY:
    raise RuntimeError(
        "SHOTSTACK_API_KEY fehlt."
    )

if not API_BASE:
    raise RuntimeError(
        "SHOTSTACK_API_BASE fehlt."
    )


def render_job(job_id: str):
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
            f"Job nicht gefunden: {job_file}"
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

    video_url = job.get("input_url")

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

    duration = end - start

    if duration <= 0:
        raise RuntimeError(
            "Ungültige Reel-Dauer."
        )

    payload = {
        "timeline": {
            "background": "#000000",
            "tracks": [
                {
                    "clips": [
                        {
                            "asset": {
                                "type": "video",
                                "src": video_url,
                                "trim": start,
                            },
                            "start": 0,
                            "length": duration,
                            "fit": "cover",
                        }
                    ]
                },
                {
                    "clips": [
                        {
                            "asset": {
                                "type": "rich-text",
                                "text": reel["hook"],
                                "font": {
                                    "size": 54,
                                    "color": "#ffffff",
                                },
                                "align": {
                                    "horizontal": "center",
                                    "vertical": "bottom",
                                },
                            },
                            "start": 0,
                            "length": min(
                                4,
                                duration,
                            ),
                        }
                    ]
                },
            ],
        },
        "output": {
            "format": "mp4",
            "aspectRatio": "9:16",
            "resolution": "preview",
        },
    }

    response = requests.post(
        f"{API_BASE}/render",
        headers={
            "x-api-key": API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    render_id = data["response"]["id"]

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_file = (
        output_dir
        / "shotstack-job.json"
    )

    result_file.write_text(
        json.dumps(
            {
                "render_id": render_id,
                "source_video": video_url,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return render_id, result_file


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("SHOTSTACK_REEL_DYNAMIC_READY")
        print(
            "USAGE: python render_reel.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    render_id, result_file = render_job(
        sys.argv[1]
    )

    print("REEL_RENDER_QUEUED")
    print(f"RENDER_ID={render_id}")
    print(f"OUTPUT={result_file}")
