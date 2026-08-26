"""Re-encode a song to the device's native audio format.

Boppo outputs 16-bit / 48 kHz / mono. We standardize every song to that so
playback needs no resample/downmix on the ESP32-S3.

Format choice (verified against the Audio Formats doc + the boppo_wasm crate):
* ``qoa`` is preferred for timing-critical playback — no start/end padding, tiny
  decode cost. It requires an external encoder (`qoaconv` from the QOA reference
  repo); we shell out to it when present.
* ``wav`` (16-bit PCM) always works via ffmpeg and is a fine fallback; it's just
  larger on the SD card.

ffmpeg does the decode/resample/downmix in both cases.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

TARGET_RATE = 48000
TARGET_CHANNELS = 1
TARGET_SAMPLE_FMT = "s16"  # 16-bit signed PCM


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise RuntimeError(f"required tool {tool!r} not found on PATH")
    return path


def have_qoaconv() -> bool:
    return shutil.which("qoaconv") is not None


def _to_wav(input_path: Path, out_wav: Path) -> None:
    """Decode/resample/downmix `input_path` to 16-bit/48k/mono WAV via ffmpeg."""
    ffmpeg = _require("ffmpeg")
    subprocess.run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-ac", str(TARGET_CHANNELS),
            "-ar", str(TARGET_RATE),
            "-sample_fmt", TARGET_SAMPLE_FMT,
            str(out_wav),
        ],
        check=True,
    )


def encode(input_path: Path, out_path: Path, fmt: str = "wav") -> Path:
    """Encode `input_path` to `out_path` in `fmt` ('wav' or 'qoa').

    Returns the path actually written. Raises with actionable guidance if the
    requested format's encoder is unavailable.
    """
    input_path = Path(input_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "wav":
        _to_wav(input_path, out_path)
        return out_path

    if fmt == "qoa":
        if not have_qoaconv():
            raise RuntimeError(
                "qoaconv not found on PATH. QOA is preferred for timing but needs "
                "an external encoder. Build it from the QOA reference repo "
                "(github.com/phoboslab/qoa: `make qoaconv`) and put it on PATH, "
                "or use --format wav for now."
            )
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "intermediate.wav"
            _to_wav(input_path, wav)
            subprocess.run([_require("qoaconv"), str(wav), str(out_path)], check=True)
        return out_path

    raise ValueError(f"unknown audio format {fmt!r}; choose 'wav' or 'qoa'")
