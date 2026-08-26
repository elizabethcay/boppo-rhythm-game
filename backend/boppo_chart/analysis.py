"""Audio onset / beat analysis via librosa.

Produces the `Onset` list and BPM that `lanes.py` turns into a chart. Kept
separate from the pure logic so the analysis stack (librosa/numpy) is only
imported when you actually process audio.
"""

from __future__ import annotations

from dataclasses import dataclass

from .lanes import Onset


@dataclass
class AnalysisResult:
    onsets: list[Onset]
    beats: list[Onset]
    beat_period_ms: float
    bpm: int
    duration_s: float
    sample_rate: int


def analyze(path: str, hop_length: int = 512) -> AnalysisResult:
    """Detect onsets, their spectral centroids, and the track BPM.

    Loads at the file's native sample rate (mono) for analysis only — the audio
    the device plays is re-encoded separately from the original in `audio.py`.
    """
    try:
        import librosa
        import numpy as np
    except ImportError as e:  # pragma: no cover - env guard
        raise RuntimeError(
            "librosa/numpy are required for audio analysis. "
            "Install the backend deps (see backend/README.md)."
        ) from e

    y, sr = librosa.load(path, sr=None, mono=True)
    duration_s = float(len(y) / sr) if sr else 0.0

    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=hop_length, backtrack=True
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

    # Spectral centroid per frame, sampled at each onset frame -> lane feature.
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    n_frames = len(centroid)

    onsets: list[Onset] = []
    for frame, t in zip(onset_frames, onset_times):
        idx = min(int(frame), n_frames - 1)
        onsets.append(
            Onset(
                time_s=float(t),
                centroid_hz=float(centroid[idx]),
                strength=float(onset_env[min(int(frame), len(onset_env) - 1)]),
            )
        )

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
    bpm = int(round(float(np.atleast_1d(tempo)[0]))) or 120

    # Beats = the song's pulse. Placing notes here (instead of on raw onsets)
    # keeps the chart aligned to the music. Sample the spectral centroid at each
    # beat so lane assignment still follows pitch.
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)
    beats = [
        Onset(
            time_s=float(t),
            centroid_hz=float(centroid[min(int(f), n_frames - 1)]),
        )
        for f, t in zip(beat_frames, beat_times)
    ]
    if len(beat_times) >= 2:
        beat_period_ms = float(np.median(np.diff(beat_times))) * 1000.0
    else:
        beat_period_ms = 60000.0 / bpm

    return AnalysisResult(
        onsets=onsets,
        beats=beats,
        beat_period_ms=beat_period_ms,
        bpm=bpm,
        duration_s=duration_s,
        sample_rate=int(sr),
    )
