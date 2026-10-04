#!/usr/bin/env python3
"""Regenerate static tour audio (intro) via ElevenLabs. Key from env / Interview-Cockpit .env."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import voice  # noqa: E402

OUT = ROOT / "app" / "static" / "audio"
SCRIPTS = {
    "intro": (
        "Welcome to VC Retail Analytics, an independent interview prototype. "
        "Synthetic dealer data is sized to Visual Comfort's public footprint — "
        "about seven hundred fifty million dollars a year across showrooms and the dealer network. "
        "Every chart number comes from a governed warehouse metric, not from free-form model guesswork. "
        "This is not a Visual Comfort production system."
    ),
}


def main():
    if not voice.configured():
        raise SystemExit("Set ELEVENLABS_API_KEY (or put it in Interview-Cockpit/.env)")
    OUT.mkdir(parents=True, exist_ok=True)
    clips = {}
    for name, text in SCRIPTS.items():
        mp3 = voice.synthesize(text)
        (OUT / f"{name}.mp3").write_bytes(mp3)
        clips[name] = {"text": text, "bytes": len(mp3)}
        print(f"wrote {name}.mp3 ({len(mp3)} bytes)")
    manifest = {
        "voice_id": voice.voice_id(),
        "voice_name": "Sarah",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clips": clips,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("manifest.json updated")


if __name__ == "__main__":
    main()
