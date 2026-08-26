"""Generate a synthetic click track for testing the pipeline end-to-end.

Writes short sine bursts at known times and ascending pitches, so onset
detection should find them and the frequency lane strategy should spread them
left-to-right. Not a musical fixture — just a deterministic signal.

    python scripts/make_click_track.py out.wav
"""

import sys

import numpy as np
import soundfile as sf

SR = 44100
CLICK_TIMES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
CLICK_FREQS = [200, 400, 800, 1500, 3000, 500, 6000, 1000]
CLICK_MS = 40


def main(out_path: str) -> None:
    n = int(SR * (CLICK_TIMES[-1] + 1.0))
    y = np.zeros(n, dtype=np.float32)
    burst = int(SR * CLICK_MS / 1000)
    env = np.hanning(burst).astype(np.float32)
    for t, f in zip(CLICK_TIMES, CLICK_FREQS):
        start = int(t * SR)
        tt = np.arange(burst) / SR
        y[start:start + burst] += 0.8 * env * np.sin(2 * np.pi * f * tt).astype(np.float32)
    sf.write(out_path, y, SR, subtype="PCM_16")
    print(f"wrote {out_path}: {len(CLICK_TIMES)} clicks, {n / SR:.1f}s @ {SR} Hz")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "click.wav")
