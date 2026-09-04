"""Build a static, synthetic-only hosted demo; never export the private journal."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build() -> None:
    source, dest = ROOT / "dashboard", ROOT / "dist"
    demo = json.loads((source / "demo.json").read_text())
    if demo["source"] != "replay" or any(
        event.get("synthetic") is not True
        for scenario in demo["scenarios"]
        for event in scenario["events"]
    ):
        raise ValueError("Only explicit synthetic replay data may be bundled")
    dest.mkdir(exist_ok=True)
    # Fixed allowlist: no .env, journal, raw market data, Python sources, or account identifiers.
    for name in ("index.html", "style.css", "app.js", "demo.json"):
        shutil.copyfile(source / name, dest / name)
    print("Built static replay dashboard (4 public files)")


if __name__ == "__main__":
    build()
