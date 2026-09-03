"""Small Featherless client. Sends only explicit payloads; never Alpaca credentials."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".local" / "llm"


def config():
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    if not values.get("FEATHERLESS_API_KEY"):
        raise RuntimeError("Add FEATHERLESS_API_KEY to the local .env file.")
    if values.get("LLM_BASE_URL", "").rstrip("/") != "https://api.featherless.ai/v1":
        raise RuntimeError("This client only sends credentials to api.featherless.ai.")
    return {
        k: values[k]
        for k in ("FEATHERLESS_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_COMPARISON_MODEL")
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(path, payload=None):
    settings = config()
    if path not in ("/models", "/plan", "/chat/completions") and not path.startswith("/models/"):
        raise ValueError("Unsupported Featherless endpoint.")
    if payload is not None and path != "/chat/completions":
        raise ValueError("Only inference POST requests are permitted.")
    req = Request(
        "https://api.featherless.ai/v1" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": "Bearer " + settings["FEATHERLESS_API_KEY"],
            "Content-Type": "application/json",
            "User-Agent": "OneSpread-eval/0.1",
        },
    )
    started = time.monotonic()
    try:
        with build_opener(NoRedirect).open(req, timeout=60) as response:
            value = json.load(response)
    except HTTPError as error:
        message = (
            error.read()
            .decode(errors="replace")
            .replace(settings["FEATHERLESS_API_KEY"], "[REDACTED]")
        )
        raise RuntimeError(f"Featherless HTTP {error.code}: {message[:1200]}") from None
    except URLError as error:
        raise RuntimeError(f"Featherless connection failed: {error.reason}") from None
    return value, round(time.monotonic() - started, 3)


def save(name, value):
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(PRIVATE / name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(value, f, indent=2)


def inspect_access():
    settings = config()
    plan, _ = request("/plan")
    save("plan.json", plan)
    result = {"authenticated_plan_request": True, "plan_fields": list(plan), "models": []}
    for model in (settings["LLM_MODEL"], settings["LLM_COMPARISON_MODEL"]):
        value, _ = request("/models/" + quote(model, safe="/"))
        save(model.replace("/", "_") + "_metadata.json", value)
        fields = (
            "id",
            "available_on_current_plan",
            "is_gated",
            "context_length",
            "max_completion_tokens",
            "pricing",
            "features",
            "status",
            "availability",
            "concurrency_cost",
        )
        result["models"].append({k: value.get(k) for k in fields})
    save("access_summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    import sys

    try:
        if len(sys.argv) == 1 or sys.argv[1] == "inspect":
            inspect_access()
        elif sys.argv[1] == "evaluate":
            from model_eval import run

            run()
        elif sys.argv[1] == "evaluate-json":
            from model_eval import run

            run("json")
        elif sys.argv[1] == "evaluate-reasoning":
            from model_eval import run

            run("reasoning-json")
        else:
            raise RuntimeError("Use inspect, evaluate, evaluate-json, or evaluate-reasoning.")
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
