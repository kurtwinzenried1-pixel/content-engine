import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.router.client import chat


def generate(job_id: str):
    job_path = ROOT / "core" / "jobs" / f"{job_id}.json"
    brand_path = ROOT / "core" / "storage" / f"{job_id}-brand.json"
    output_dir = ROOT / "exports" / job_id / "content"

    if not job_path.exists():
        raise FileNotFoundError(
            f"Job nicht gefunden: {job_path}"
        )

    job = json.loads(
        job_path.read_text(encoding="utf-8-sig")
    )

    if brand_path.exists():
        brand = json.loads(
            brand_path.read_text(encoding="utf-8-sig")
        )
    else:
        brand = {
            "company": job["company"],
            "industry": job.get("industry", "Nicht angegeben"),
            "target_audience": job.get(
                "target_audience",
                "Kunden des Unternehmens"
            ),
            "tone": job.get(
                "tone",
                "professionell, klar und modern"
            ),
            "language": job.get("language", "de"),
            "cta": job.get("cta", ""),
            "products_services": job.get(
                "products_services",
                []
            ),
            "usps": job.get("usps", [])
        }

    quantity = int(job["quantity"])

    if quantity < 1:
        raise RuntimeError(
            "quantity muss mindestens 1 sein."
        )

    system = """
Du bist eine professionelle Social-Media-Content-Engine.
Du erzeugst präzise, abwechslungsreiche und markenkonforme Inhalte.
Antworte ausschließlich mit gültigem JSON.
Keine Markdown-Codeblöcke und keine Erklärungen.
"""

    prompt = f"""
Erstelle exakt {quantity} unterschiedliche Social-Media-Posts.

Firma: {brand["company"]}
Branche: {brand["industry"]}
Zielgruppe: {brand["target_audience"]}
Tonalität: {brand["tone"]}
Sprache: {brand["language"]}
CTA: {brand.get("cta", "")}
Produkte/Services: {", ".join(brand.get("products_services", []))}
USPs: {", ".join(brand.get("usps", []))}

Regeln:
- Keine erfundenen Unternehmensfakten.
- Keine übertriebenen Versprechen.
- Jeder Post braucht einen anderen inhaltlichen Ansatz.
- Jeder Post braucht Hook, Caption, CTA und exakt 5 Hashtags.
- Schreibe in der angegebenen Sprache.

Liefere exakt dieses JSON-Schema:

{{
  "posts": [
    {{
      "number": 1,
      "hook": "...",
      "caption": "...",
      "cta": "...",
      "hashtags": [
        "#eins",
        "#zwei",
        "#drei",
        "#vier",
        "#fuenf"
      ]
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
        max_tokens=min(
            12000,
            max(1800, quantity * 400)
        )
    )

    content = json.loads(raw.strip())
    posts = content.get("posts", [])

    if len(posts) != quantity:
        raise RuntimeError(
            f"Erwartet: {quantity} Posts | erhalten: {len(posts)}"
        )

    for index, post in enumerate(posts, start=1):
        required = {
            "number",
            "hook",
            "caption",
            "cta",
            "hashtags"
        }

        missing = required - set(post.keys())

        if missing:
            raise RuntimeError(
                f"Post {index}: Felder fehlen: {sorted(missing)}"
            )

        if len(post["hashtags"]) != 5:
            raise RuntimeError(
                f"Post {index}: Erwartet 5 Hashtags."
            )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = output_dir / "social-posts.json"

    output_file.write_text(
        json.dumps(
            content,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return output_file, len(posts)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("SOCIAL_ENGINE_DYNAMIC_READY")
        print(
            "USAGE: python generate_social.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    output_file, count = generate(sys.argv[1])

    print(
        f"CONTENT_ENGINE_READY: {count} Posts"
    )
    print("MODEL_ROUTE: content-bulk")
    print(f"OUTPUT: {output_file}")
