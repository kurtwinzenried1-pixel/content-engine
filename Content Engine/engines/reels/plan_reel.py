import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.router.client import chat


def plan(job_id: str):
    output_dir = ROOT / "exports" / job_id
    transcript_file = output_dir / "transcript.json"

    if not transcript_file.exists():
        raise FileNotFoundError(
            f"Transkript fehlt: {transcript_file}"
        )

    transcript = json.loads(
        transcript_file.read_text(
            encoding="utf-8-sig"
        )
    )

    segments = transcript.get(
        "segments",
        []
    )

    if not segments:
        raise RuntimeError(
            "Transkript enthält keine Segmente mit Zeitstempeln."
        )

    system = """
Du bist eine professionelle Short-Form-Video-Editor-Engine.
Du wählst aus Transkriptsegmenten die stärksten Stellen für Reels und Shorts.
Priorisiere Hook, Verständlichkeit, konkreten Nutzen und hohe Informationsdichte.
Antworte ausschließlich mit gültigem JSON.
"""

    prompt = f"""
Wähle aus diesem Transkript die beste Sequenz für ein Social-Media-Reel.

TRANSKRIPT:
{json.dumps(segments, ensure_ascii=False)}

Ziel:
- 15 bis 30 Sekunden
- sofort verständlicher Einstieg
- starke erste Aussage
- kein unnötiges Intro
- zusammenhängender Gedanke
- natürliche Schnittpunkte

Liefere exakt:

{{
  "reel": {{
    "title": "...",
    "hook": "...",
    "start": 0.0,
    "end": 20.0,
    "duration": 20.0,
    "subtitle_style": "clean-bold",
    "aspect_ratio": "9:16",
    "caption": "...",
    "cta": "..."
  }}
}}
"""

    raw = chat(
        prompt=prompt,
        model="content-bulk",
        system=system,
        timeout=180,
        json_mode=True,
        disable_thinking=True,
        max_tokens=800,
    )

    data = json.loads(
        raw.strip()
    )

    reel = data.get("reel")

    if not reel:
        raise RuntimeError(
            "Kein Reel-Plan erhalten."
        )

    required = [
        "title",
        "hook",
        "start",
        "end",
        "duration",
        "subtitle_style",
        "aspect_ratio",
        "caption",
        "cta",
    ]

    missing = [
        key
        for key in required
        if key not in reel
    ]

    if missing:
        raise RuntimeError(
            f"Fehlende Reel-Felder: {missing}"
        )

    reel["start"] = float(
        reel["start"]
    )

    reel["end"] = float(
        reel["end"]
    )

    reel["duration"] = (
        reel["end"]
        - reel["start"]
    )

    if reel["duration"] <= 0:
        raise RuntimeError(
            "Ungültige Schnittzeiten."
        )

    output = (
        output_dir
        / "reel-plan.json"
    )

    output.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output, reel


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("REEL_PLANNER_DYNAMIC_READY")
        print(
            "USAGE: python plan_reel.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    output, reel = plan(
        sys.argv[1]
    )

    print("REEL_PLANNER_READY")
    print(
        f"CUT: {reel['start']}s -> {reel['end']}s"
    )
    print(
        f"DURATION: {reel['duration']}s"
    )
    print(
        f"FORMAT: {reel['aspect_ratio']}"
    )
    print(
        f"OUTPUT: {output}"
    )
