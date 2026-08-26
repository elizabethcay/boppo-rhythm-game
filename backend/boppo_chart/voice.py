"""Generate spoken song-name clips for the menu's announce-then-confirm flow.

Uses macOS `say` to synthesize the name, then re-encodes to the device format
via `audio.encode` (same 16-bit / 48 kHz / mono target as songs). macOS only.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import audio


def have_say() -> bool:
    return shutil.which("say") is not None


def spoken_name(song_id: str) -> str:
    """Turn a song id slug into text to speak, e.g. 'what-it-sounds-like'."""
    return song_id.replace("-", " ").replace("_", " ").strip() or song_id


def synthesize(text: str, out_path: Path, fmt: str = "wav", voice: str | None = None) -> Path:
    """Synthesize `text` to `out_path` in the device audio format."""
    if not have_say():
        raise RuntimeError(
            "macOS `say` not found — it's needed to generate song-name voice clips. "
            "(This step is macOS-only.)"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "name.aiff"
        cmd = ["say", "-o", str(aiff)]
        if voice:
            cmd += ["-v", voice]
        cmd += [text]
        subprocess.run(cmd, check=True)
        audio.encode(aiff, out_path, fmt=fmt)
    return out_path
