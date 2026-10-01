import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.router.client import chat


def generate(job_id: str):
    job_file = ROOT / "core" / "jobs" / f"{job_id}.json"
    brand_file = ROOT / "core" / "storage" / f"{job_id}-brand.json"
    posts_file = ROOT / "exports" / job_id / "content" / "social-posts.json"
    output_dir = ROOT / "exports" / job_id / "graphics"

    if not job_file.exists():
        raise FileNotFoundError(
            f"Job nicht gefunden: {job_file}"
        )

    if not posts_file.exists():
        raise FileNotFoundError(
            f"Social Posts fehlen: {posts_file}"
        )

    job = json.loads(
        job_file.read_text(encoding="utf-8-sig")
    )

    posts = json.loads(
        posts_file.read_text(encoding="utf-8-sig")
    )["posts"]

    if brand_file.exists():
        brand = json.loads(
            brand_file.read_text(encoding="utf-8-sig")
        )
    else:
        brand = {
            "company": job["company"],
            "industry": job.get(
                "industry",
                "Nicht angegeben"
            ),
            "tone": job.get(
                "tone",
                "professionell, klar und modern"
            ),
            "brand_colors": job.get(
                "brand_colors",
                ["#111111", "#FFFFFF"]
            )
        }

    system = """
Du bist eine professionelle Creative-Director-Engine.
Erstelle aus Social-Media-Posts klare und hochwertige Visual Briefs.
Antworte ausschließlich mit gültigem JSON.
Keine Erklärungen und kein Markdown.
"""

    prompt = f"""
Marke:
Firma: {brand["company"]}
Branche: {brand["industry"]}
Tonalität: {brand["tone"]}
Farben: {", ".join(brand.get("brand_colors", []))}

Posts:
{json.dumps(posts, ensure_ascii=False)}

Erstelle für jeden Post exakt einen Visual Brief.

Jeder Brief braucht:
- post_number
- concept
- image_prompt
- headline
- layout
- aspect_ratio
- avoid

Regeln:
- professioneller Social-Media-Look
- keine erfundenen Logos
- keine Wasserzeichen
- keine zusätzlichen Texte außer der Headline
- konsistenter Markenstil
- aspect_ratio immer "1:1"

Liefere exakt:

{{
  "visuals": [
    {{
      "post_number": 1,
      "concept": "...",
      "image_prompt": "...",
      "headline": "...",
      "layout": "...",
      "aspect_ratio": "1:1",
      "avoid": "..."
    }}
  ]
}}
"""

    raw = chat(
        prompt=prompt,
        model="content-bulk",
        system=system,
        timeout=180,
        json_mode=True,
        disable_thinking=True,
        max_tokens=max(
            1600,
            len(posts) * 500
        )
    )

    data = json.loads(raw.strip())
    visuals = data.get("visuals", [])

    if len(visuals) != len(posts):
        raise RuntimeError(
            f"Erwartet {len(posts)} Visuals, "
            f"erhalten {len(visuals)}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output = output_dir / "visual-briefs.json"

    output.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return output, visuals


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("CREATIVE_ENGINE_DYNAMIC_READY")
        print(
            "USAGE: python generate_visual_briefs.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    output, visuals = generate(sys.argv[1])

    print(
        f"CREATIVE_ENGINE_READY: {len(visuals)} Visual Briefs"
    )
    print(f"OUTPUT: {output}")
