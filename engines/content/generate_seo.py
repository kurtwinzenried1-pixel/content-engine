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
            "cta": job.get("cta", "")
        }

    keyword = job.get("keyword")

    if not keyword:
        industry = brand.get("industry", "")
        keyword = (
            f"{industry} Schweiz"
            if industry and industry != "Nicht angegeben"
            else f"{brand['company']} Schweiz"
        )

    system = """
/no_think
Du bist eine schnelle professionelle SEO-Content-Engine.
Schreibe direkt und ohne lange interne Analyse.
Antworte ausschließlich mit gültigem JSON.
Keine Markdown-Codeblöcke.
Keine erfundenen Fakten, Statistiken oder Quellen.
"""

    prompt = f"""
/no_think

Erstelle einen kompakten SEO-Blogartikel.

Firma: {brand["company"]}
Branche: {brand["industry"]}
Zielgruppe: {brand["target_audience"]}
Tonalität: {brand["tone"]}
Sprache: {brand["language"]}
Keyword: {keyword}

Vorgaben:
- Einleitung: 60-100 Wörter
- exakt 4 Hauptabschnitte
- pro Abschnitt 80-120 Wörter
- exakt 3 FAQs
- jede FAQ-Antwort 30-60 Wörter
- natürliche Keyword-Verwendung
- keine erfundenen Zahlen oder Referenzen

Liefere ausschließlich:

{{
  "keyword": "...",
  "meta_title": "...",
  "meta_description": "...",
  "title": "...",
  "introduction": "...",
  "sections": [
    {{
      "heading": "...",
      "text": "..."
    }}
  ],
  "faq": [
    {{
      "question": "...",
      "answer": "..."
    }}
  ],
  "cta": "..."
}}
"""

    raw = chat(
        prompt=prompt,
        model="content-bulk",
        system=system,
        timeout=180,
        json_mode=True,
        disable_thinking=True,
        max_tokens=3200
    )

    article = json.loads(raw.strip())

    required = [
        "keyword",
        "meta_title",
        "meta_description",
        "title",
        "introduction",
        "sections",
        "faq",
        "cta"
    ]

    missing = [
        field
        for field in required
        if not article.get(field)
    ]

    if missing:
        raise RuntimeError(
            f"Fehlende Felder: {missing}"
        )

    if len(article["sections"]) != 4:
        raise RuntimeError(
            f"Erwartet 4 Sections, erhalten {len(article['sections'])}"
        )

    if len(article["faq"]) != 3:
        raise RuntimeError(
            f"Erwartet 3 FAQs, erhalten {len(article['faq'])}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output = output_dir / "seo-article.json"

    output.write_text(
        json.dumps(
            article,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return output, article


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("SEO_ENGINE_DYNAMIC_READY")
        print(
            "USAGE: python generate_seo.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    output, article = generate(sys.argv[1])

    print("SEO_ENGINE_READY: 1 Artikel")
    print(f"SECTIONS: {len(article['sections'])}")
    print(f"FAQ: {len(article['faq'])}")
    print(f"OUTPUT: {output}")
