import json
import os
import urllib.request
from pathlib import Path

root = Path.cwd()

for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

payload = {
    "model": "content-bulk",
    "messages": [
        {
            "role": "user",
            "content": 'Gib ausschließlich dieses JSON zurück: {"status":"SEO_JSON_READY"}'
        }
    ],
    "chat_template_kwargs": {
        "enable_thinking": False
    },
    "response_format": {
        "type": "json_object"
    },
    "max_tokens": 200
}

req = urllib.request.Request(
    "http://localhost:4000/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {os.environ['LITELLM_MASTER_KEY']}",
        "Content-Type": "application/json"
    },
    method="POST"
)

with urllib.request.urlopen(req, timeout=120) as r:
    data = json.loads(r.read().decode("utf-8"))

print("CONTENT:")
print(data["choices"][0]["message"]["content"])
