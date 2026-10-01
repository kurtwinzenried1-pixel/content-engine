import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "exports" / "JOB-0001" / "content" / "social-posts.json"

data = json.loads(FILE.read_text(encoding="utf-8-sig"))
posts = data.get("posts", [])

errors = []

if not posts:
    errors.append("Keine Posts vorhanden.")

hooks = set()
captions = set()

for i, post in enumerate(posts, start=1):
    for field in ["hook", "caption", "cta", "hashtags"]:
        if field not in post or not post[field]:
            errors.append(f"Post {i}: {field} fehlt.")

    if len(post.get("hashtags", [])) != 5:
        errors.append(f"Post {i}: nicht exakt 5 Hashtags.")

    hook = post.get("hook", "").strip().lower()
    caption = post.get("caption", "").strip().lower()

    if hook in hooks:
        errors.append(f"Post {i}: Hook-Duplikat.")
    hooks.add(hook)

    if caption in captions:
        errors.append(f"Post {i}: Caption-Duplikat.")
    captions.add(caption)

if errors:
    print("QA_FAILED")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print(f"QA_READY: {len(posts)} Posts geprüft")
print("RESULT: PASS")
