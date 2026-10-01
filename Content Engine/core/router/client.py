import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

def load_env():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

load_env()

LITELLM_URL = os.getenv(
    "LITELLM_URL",
    "http://localhost:4000/v1/chat/completions"
)

LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY")

def chat(
    prompt,
    model="content-bulk",
    system=None,
    timeout=600,
    json_mode=False,
    disable_thinking=False,
    max_tokens=None
):
    if not LITELLM_MASTER_KEY:
        raise RuntimeError("LITELLM_MASTER_KEY fehlt.")

    messages = []

    if system:
        messages.append({
            "role": "system",
            "content": system
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

    payload = {
        "model": model,
        "messages": messages
    }

    if json_mode:
        payload["response_format"] = {
            "type": "json_object"
        }

    if disable_thinking:
        payload["chat_template_kwargs"] = {
            "enable_thinking": False
        }

    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    request = urllib.request.Request(
        LITELLM_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    return result["choices"][0]["message"]["content"]

if __name__ == "__main__":
    response = chat(
        'Gib ausschließlich dieses JSON zurück: {"status":"ROUTER_JSON_READY"}',
        model="content-bulk",
        json_mode=True,
        disable_thinking=True,
        max_tokens=200
    )

    print(response)
