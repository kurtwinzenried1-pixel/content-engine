import json
import os
import sys
import tempfile
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


API_KEY = os.getenv("TOGETHER_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "TOGETHER_API_KEY fehlt."
    )


def transcribe_file(file_path, language=None):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    data = {
        "model": "openai/whisper-large-v3",
        "response_format": "json",
        "timestamp_granularities": "segment",
    }

    if language:
        data["language"] = language

    with path.open("rb") as media:
        response = requests.post(
            "https://api.together.xyz/v1/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {API_KEY}"
            },
            data=data,
            files={
                "file": (
                    path.name,
                    media,
                )
            },
            timeout=600,
        )

    response.raise_for_status()

    return response.json()


def transcribe_job(job_id):
    job_file = (
        ROOT
        / "core"
        / "jobs"
        / f"{job_id}.json"
    )

    if not job_file.exists():
        raise FileNotFoundError(
            f"Job nicht gefunden: {job_file}"
        )

    job = json.loads(
        job_file.read_text(
            encoding="utf-8-sig"
        )
    )

    input_url = job.get("input_url")

    if not input_url:
        raise RuntimeError(
            "Reels-Job braucht input_url."
        )

    suffix = Path(
        input_url.split("?")[0]
    ).suffix or ".mp4"

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as tmp:
        temp_path = Path(tmp.name)

    try:
        with requests.get(
            input_url,
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()

            with temp_path.open("wb") as file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)

        result = transcribe_file(
            temp_path,
            language=job.get("language"),
        )

        output_dir = (
            ROOT
            / "exports"
            / job_id
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output = output_dir / "transcript.json"

        output.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return output, result

    finally:
        temp_path.unlink(
            missing_ok=True
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("WHISPER_ENGINE_DYNAMIC_READY")
        print(
            "USAGE: python transcribe.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    output, result = transcribe_job(
        sys.argv[1]
    )

    print("WHISPER_TRANSCRIPTION_READY")
    print(f"OUTPUT: {output}")
