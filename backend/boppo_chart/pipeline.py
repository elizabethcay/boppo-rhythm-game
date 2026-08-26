"""Shared pipeline steps: analyze -> chart -> library -> compiled activity.

`cli.py` composes these into `build` (a single chart) and `bundle` (a whole
song library compiled into one activity wasm).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .chart import Chart
from .codegen import SongSpec, write_songs_rust
from .lanes import build_notes, build_notes_from_beats

# repo layout: <root>/backend/boppo_chart/pipeline.py -> <root>/frontend
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRONTEND = _REPO_ROOT / "frontend"
WASM_TARGET = "wasm32-wasip1"
BUILT_WASM_REL = f"target/{WASM_TARGET}/release/rhythm_game.wasm"


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "song"


@dataclass
class SongResult:
    spec: SongSpec
    audio_path: Path
    name_path: Path
    chart_json: Path
    info: dict


@dataclass
class BundleArtifacts:
    out_dir: Path
    songs_rs: Path
    songs: list[SongResult]
    wasm: Path | None = None
    extra: dict = field(default_factory=dict)

    @property
    def audio_paths(self) -> list[Path]:
        return [s.audio_path for s in self.songs]


def analyze_to_chart(
    input_path: Path,
    song_id: str,
    *,
    lanes: str = "freq",
    min_gap_ms: float = 90.0,
    lead_ms: int = 500,
    window_ms: int = 150,
    sync: str = "beat",
) -> tuple[Chart, dict]:
    """Run analysis + note placement into a validated `Chart` (+ info dict).

    `sync="beat"` snaps notes to the song's beat grid (musical, recommended);
    `sync="onset"` places them on detected transients (busier, can feel off-beat).
    """
    from . import analysis  # deferred: heavy deps

    result = analysis.analyze(str(input_path))
    if sync == "beat":
        notes = build_notes_from_beats(
            result.beats, result.beat_period_ms, strategy=lanes, min_gap_ms=min_gap_ms
        )
    elif sync == "onset":
        notes = build_notes(result.onsets, strategy=lanes, min_gap_ms=min_gap_ms)
    else:
        raise ValueError(f"unknown sync mode {sync!r}; choose 'beat' or 'onset'")
    chart = Chart(
        song_id=song_id,
        bpm=result.bpm,
        lead_time_ms=lead_ms,
        hit_window_ms=window_ms,
        notes=notes,
    )
    chart.validate()
    info = {
        "onsets": len(result.onsets),
        "notes": len(notes),
        "bpm": result.bpm,
        "duration_s": result.duration_s,
        "sample_rate": result.sample_rate,
    }
    return chart, info


def _unique_song_id(preferred: str, taken: set[str]) -> str:
    song_id = preferred
    n = 2
    while song_id in taken:
        song_id = f"{preferred}-{n}"
        n += 1
    taken.add(song_id)
    return song_id


def process_songs(
    inputs: list[Path],
    out_dir: Path,
    *,
    lanes: str = "freq",
    min_gap_ms: float = 90.0,
    lead_ms: int = 500,
    window_ms: int = 150,
    sync: str = "beat",
    audio_format: str = "wav",
    name_clips: dict[str, str] | None = None,
    on_progress=None,
) -> list[SongResult]:
    """Analyze + encode each input into `out_dir`, returning per-song results.

    Audio lands in `out_dir/songs/<id>.<ext>` and each `SongSpec.audio_file` is
    the device-relative path the activity plays. Name clips come from
    `name_clips` (song id -> local audio path) when provided, else macOS TTS.
    """
    from . import audio, voice  # deferred: need ffmpeg / macOS say

    name_clips = name_clips or {}

    songs_dir = out_dir / "songs"
    names_dir = out_dir / "names"
    charts_dir = out_dir / "charts"
    songs_dir.mkdir(parents=True, exist_ok=True)
    names_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    taken: set[str] = set()
    results: list[SongResult] = []
    for input_path in inputs:
        input_path = Path(input_path)
        song_id = _unique_song_id(slug(input_path.stem), taken)
        if on_progress:
            on_progress(song_id, input_path)

        chart, info = analyze_to_chart(
            input_path, song_id,
            lanes=lanes, min_gap_ms=min_gap_ms, lead_ms=lead_ms, window_ms=window_ms,
            sync=sync,
        )

        chart_json = charts_dir / f"{song_id}.chart.json"
        chart.write_json(chart_json)

        audio_rel = f"songs/{song_id}.{audio_format}"
        audio_path = out_dir / audio_rel
        audio.encode(input_path, audio_path, fmt=audio_format)

        # Spoken-name clip for the announce-then-confirm menu: a custom recording
        # if one was provided for this song id, otherwise macOS TTS.
        name_rel = f"names/{song_id}.{audio_format}"
        name_path = out_dir / name_rel
        if song_id in name_clips:
            audio.encode(Path(name_clips[song_id]), name_path, fmt=audio_format)
        else:
            voice.synthesize(voice.spoken_name(song_id), name_path, fmt=audio_format)

        results.append(
            SongResult(
                spec=SongSpec(
                    id=song_id, audio_file=audio_rel, name_audio=name_rel, chart=chart
                ),
                audio_path=audio_path,
                name_path=name_path,
                chart_json=chart_json,
                info=info,
            )
        )
    return results


def _find_cargo(explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which("cargo")
    if found:
        return found
    fallback = Path.home() / ".cargo" / "bin" / "cargo"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError(
        "cargo not found. Install Rust (https://rustup.rs) or pass --cargo PATH."
    )


def compile_activity(
    songs_rs: Path,
    dest_wasm: Path,
    *,
    frontend_dir: Path = DEFAULT_FRONTEND,
    cargo: str | None = None,
) -> Path:
    """Compile the frontend with the given song library injected, copy the wasm.

    Sets `BOPPO_SONGS_RS` so the frontend's build.rs compiles `songs_rs` in as
    `SONGS`.
    """
    frontend_dir = Path(frontend_dir)
    if not (frontend_dir / "Cargo.toml").exists():
        raise RuntimeError(f"frontend crate not found at {frontend_dir}")
    cargo_bin = _find_cargo(cargo)

    env = os.environ.copy()
    env["BOPPO_SONGS_RS"] = str(Path(songs_rs).resolve())
    cargo_dir = str(Path(cargo_bin).resolve().parent)
    env["PATH"] = cargo_dir + os.pathsep + env.get("PATH", "")

    subprocess.run(
        [cargo_bin, "build", "--release", "--target", WASM_TARGET],
        cwd=str(frontend_dir),
        env=env,
        check=True,
    )

    built = frontend_dir / BUILT_WASM_REL
    if not built.exists():
        raise RuntimeError(f"expected wasm not found: {built}")
    dest_wasm = Path(dest_wasm)
    dest_wasm.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, dest_wasm)
    return dest_wasm


def bundle(
    inputs: list[Path],
    out_root: Path,
    name: str,
    *,
    lanes: str = "freq",
    min_gap_ms: float = 90.0,
    lead_ms: int = 500,
    window_ms: int = 150,
    sync: str = "beat",
    audio_format: str = "wav",
    name_clips: dict[str, str] | None = None,
    frontend_dir: Path = DEFAULT_FRONTEND,
    cargo: str | None = None,
    compile: bool = True,
    on_progress=None,
) -> BundleArtifacts:
    """Full multi-song pipeline: analyze all inputs, codegen the library, compile."""
    out_dir = Path(out_root) / name
    out_dir.mkdir(parents=True, exist_ok=True)

    songs = process_songs(
        inputs, out_dir,
        lanes=lanes, min_gap_ms=min_gap_ms, lead_ms=lead_ms, window_ms=window_ms,
        sync=sync, audio_format=audio_format, name_clips=name_clips,
        on_progress=on_progress,
    )

    songs_rs = out_dir / "songs_generated.rs"
    write_songs_rust([s.spec for s in songs], songs_rs)

    artifacts = BundleArtifacts(out_dir=out_dir, songs_rs=songs_rs, songs=songs)
    if compile:
        artifacts.wasm = compile_activity(
            songs_rs, out_dir / "rhythm_game.wasm",
            frontend_dir=frontend_dir, cargo=cargo,
        )
    return artifacts
