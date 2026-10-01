import html
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def render(job_id: str):
    job_file = ROOT / "core" / "jobs" / f"{job_id}.json"
    brand_file = ROOT / "core" / "storage" / f"{job_id}-brand.json"
    briefs_file = ROOT / "exports" / job_id / "graphics" / "visual-briefs.json"
    output_dir = ROOT / "exports" / job_id / "graphics" / "rendered"

    if not job_file.exists():
        raise FileNotFoundError(
            f"Job nicht gefunden: {job_file}"
        )

    if not briefs_file.exists():
        raise FileNotFoundError(
            f"Visual Briefs fehlen: {briefs_file}"
        )

    job = json.loads(
        job_file.read_text(encoding="utf-8-sig")
    )

    briefs = json.loads(
        briefs_file.read_text(encoding="utf-8-sig")
    )["visuals"]

    if brand_file.exists():
        brand = json.loads(
            brand_file.read_text(encoding="utf-8-sig")
        )
    else:
        brand = {
            "company": job["company"],
            "brand_colors": job.get(
                "brand_colors",
                ["#111111", "#FFFFFF"]
            )
        }

    colors = brand.get(
        "brand_colors",
        ["#111111", "#FFFFFF"]
    )

    bg = colors[0] if colors else "#111111"
    fg = colors[1] if len(colors) > 1 else "#FFFFFF"

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    files = []

    for visual in briefs:
        number = int(visual["post_number"])
        headline = visual.get("headline", "").strip()
        concept = visual.get("concept", "").strip()

        lines = textwrap.wrap(
            headline,
            width=24
        )[:4]

        text_svg = ""
        start_y = 390

        for index, line in enumerate(lines):
            y = start_y + index * 78

            text_svg += (
                f'<text x="540" y="{y}" '
                f'text-anchor="middle" '
                f'font-family="Arial, Helvetica, sans-serif" '
                f'font-size="64" font-weight="700" '
                f'fill="{html.escape(fg)}">'
                f'{html.escape(line)}</text>'
            )

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg"
width="1080" height="1080" viewBox="0 0 1080 1080">

<rect width="1080" height="1080" fill="{html.escape(bg)}"/>

<circle cx="910" cy="170" r="220"
fill="{html.escape(fg)}" opacity="0.07"/>

<circle cx="120" cy="930" r="260"
fill="{html.escape(fg)}" opacity="0.05"/>

<text x="80" y="100"
font-family="Arial, Helvetica, sans-serif"
font-size="30"
font-weight="600"
fill="{html.escape(fg)}">
{html.escape(brand["company"])}
</text>

{text_svg}

<text x="540" y="860"
text-anchor="middle"
font-family="Arial, Helvetica, sans-serif"
font-size="25"
fill="{html.escape(fg)}"
opacity="0.72">
{html.escape(concept[:90])}
</text>

<rect x="80" y="950" width="180" height="6"
fill="{html.escape(fg)}"/>

</svg>'''

        file = output_dir / f"post-{number:02}.svg"

        file.write_text(
            svg,
            encoding="utf-8"
        )

        files.append(file)

    return output_dir, files


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("GRAPHICS_RENDERER_DYNAMIC_READY")
        print(
            "USAGE: python render_graphics.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    output_dir, files = render(sys.argv[1])

    print(
        f"GRAPHICS_RENDERER_READY: {len(files)} Grafiken"
    )
    print(f"OUTPUT: {output_dir}")
