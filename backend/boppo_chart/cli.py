"""Command-line entry point: `python -m boppo_chart ...`.

    build  INPUT...          analyze song(s) -> charts + audio + songs_generated.rs
    bundle INPUT...          build + compile the activity wasm (one command),
                             optionally uploading the whole library to a tablet
    upload SERIAL            push an already-built activity + song(s) to a tablet

`build` and `bundle` both accept multiple songs; the activity shows one song per
button and plays the one the player picks.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import difficulty, pipeline
from .lanes import STRATEGIES


def _default_name(inputs: list[str]) -> str:
    if len(inputs) == 1:
        return pipeline.slug(Path(inputs[0]).stem)
    return "library"


def _progress(song_id: str, path: Path) -> None:
    print(f"[analyze] {song_id:<16} <- {path.name}")


def _run_bundle(args: argparse.Namespace, *, compile: bool):
    inputs = [Path(p) for p in args.input]
    missing = [str(p) for p in inputs if not p.exists()]
    if missing:
        print(f"error: input(s) not found: {', '.join(missing)}", file=sys.stderr)
        return None

    name = args.name or _default_name(args.input)

    name_clips: dict[str, str] = {}
    for item in getattr(args, "name_audio", None) or []:
        if "=" not in item:
            print(f"error: --name-audio must be ID=PATH, got {item!r}", file=sys.stderr)
            return None
        sid, path = item.split("=", 1)
        clip = Path(path)
        if not clip.exists():
            print(f"error: name clip not found: {clip}", file=sys.stderr)
            return None
        name_clips[sid] = str(clip)

    min_gap_ms, lead_ms, window_ms = difficulty.resolve(
        args.difficulty,
        min_gap_ms=args.min_gap_ms, lead_ms=args.lead_ms, window_ms=args.window_ms,
    )
    print(f"[config]  difficulty={args.difficulty} "
          f"(min_gap={min_gap_ms:.0f}ms, lead={lead_ms}ms, window={window_ms}ms), "
          f"sync={args.sync}, lanes={args.lanes}")
    artifacts = pipeline.bundle(
        inputs, Path(args.out), name,
        lanes=args.lanes, min_gap_ms=min_gap_ms,
        lead_ms=lead_ms, window_ms=window_ms,
        sync=args.sync, audio_format=args.format, name_clips=name_clips,
        frontend_dir=Path(getattr(args, "frontend", pipeline.DEFAULT_FRONTEND)),
        cargo=getattr(args, "cargo", None),
        compile=compile,
        on_progress=_progress,
    )
    if name_clips:
        print(f"[names]   custom clips for: {', '.join(sorted(name_clips))}")
    total_notes = sum(s.info["notes"] for s in artifacts.songs)
    print(f"[library] {len(artifacts.songs)} song(s), {total_notes} notes total "
          f"-> {artifacts.out_dir}/")
    return artifacts


def _cmd_build(args: argparse.Namespace) -> int:
    artifacts = _run_bundle(args, compile=False)
    if artifacts is None:
        return 1
    print(f"charts + audio + {artifacts.songs_rs.name} written (no wasm; use `bundle` to compile)")
    return 0


def _cmd_bundle(args: argparse.Namespace) -> int:
    print("[compile] building the activity wasm with this library ...")
    try:
        artifacts = _run_bundle(args, compile=True)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if artifacts is None:
        return 1

    size_kb = artifacts.wasm.stat().st_size / 1024
    print(f"          -> {artifacts.wasm} ({size_kb:.0f} KB)")

    if args.upload:
        from . import upload

        password = args.password
        if args.pair or not password:
            print(f"[upload]  pairing with boppo-{args.upload}.local — approve on device ...")
            password = upload.pair(args.upload)
        print(f"[upload]  pushing activity + {len(artifacts.songs)} song(s) + names ...")
        upload.upload_bundle_dir(
            args.upload, password, artifacts.out_dir, artifacts.wasm,
            activity=args.activity,
            on_file=lambda n: print(f"          - {n}"),
        )
        print("          upload complete.")
        if args.launch:
            out = upload.start_activity(args.upload, password, activity=args.activity)
            print(f"[launch]  started '{args.activity}': {out.strip()}")
    else:
        print(f"\nbundle ready in {artifacts.out_dir}/")
        audio_args = " ".join(f"--audio {p}" for p in artifacts.audio_paths)
        print(f"upload with:  python -m boppo_chart upload <SERIAL> "
              f"--wasm {artifacts.wasm} {audio_args}")
    return 0


def _resolve_password(upload_mod, serial, password, force_pair):
    if force_pair or not password:
        print(f"pairing with boppo-{serial}.local — approve on the device ...")
        password = upload_mod.pair(serial)
    return password


def _cmd_launch(args: argparse.Namespace) -> int:
    from . import upload

    password = _resolve_password(upload, args.serial, args.password, args.pair)
    out = upload.start_activity(args.serial, password, activity=args.activity)
    print(f"launched '{args.activity}': {out.strip()}")
    return 0


def _cmd_upload(args: argparse.Namespace) -> int:
    from . import upload

    password = args.password
    if args.pair or not password:
        print(f"pairing with boppo-{args.serial}.local — approve on the device ...")
        password = upload.pair(args.serial)
        print("paired.")

    upload.upload_activity(
        args.serial, password, Path(args.wasm), [Path(a) for a in args.audio],
        activity=args.activity,
    )
    print("upload complete.")
    return 0


def _add_chart_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", nargs="+", help="input audio file(s) (mp3/wav/flac/...)")
    p.add_argument("--out", default="dist", help="output directory (default: dist)")
    p.add_argument("--name", default=None,
                   help="library folder name (default: song id, or 'library')")
    p.add_argument("--difficulty", choices=list(difficulty.DIFFICULTIES),
                   default=difficulty.DEFAULT,
                   help=f"pacing preset (default: {difficulty.DEFAULT})")
    p.add_argument("--sync", choices=["beat", "onset"], default="beat",
                   help="place notes on the beat grid (musical) or on raw onsets")
    p.add_argument("--lanes", choices=sorted(STRATEGIES), default="freq")
    # These override the difficulty preset when given; default None = use preset.
    p.add_argument("--min-gap-ms", type=float, default=None,
                   help="override: min time between notes (higher = sparser)")
    p.add_argument("--lead-ms", type=int, default=None,
                   help="override: preview lead time (higher = more warning)")
    p.add_argument("--window-ms", type=int, default=None,
                   help="override: hit window width (higher = more lenient)")
    p.add_argument("--format", choices=["wav", "qoa"], default="wav",
                   help="device audio format (qoa preferred, needs qoaconv)")
    p.add_argument("--name-audio", action="append", default=[], metavar="ID=PATH",
                   help="custom spoken-name clip for a song id (repeatable); "
                        "songs without one fall back to TTS")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="boppo_chart", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="analyze song(s) into charts + assets (no compile)")
    _add_chart_opts(b)
    b.set_defaults(func=_cmd_build)

    n = sub.add_parser("bundle", help="build + compile the activity wasm (one command)")
    _add_chart_opts(n)
    n.add_argument("--frontend", default=str(pipeline.DEFAULT_FRONTEND),
                   help="path to the frontend crate")
    n.add_argument("--cargo", default=None, help="path to cargo (default: autodetect)")
    n.add_argument("--upload", metavar="SERIAL", default=None,
                   help="also upload to boppo-<SERIAL>.local after compiling")
    n.add_argument("--launch", action="store_true",
                   help="start the activity on the device after upload")
    n.add_argument("--activity", default="rhythm_game", help="activity package/folder name")
    n.add_argument("--password", default=None, help="bearer password for --upload")
    n.add_argument("--pair", action="store_true", help="force re-pair for --upload")
    n.set_defaults(func=_cmd_bundle)

    la = sub.add_parser("launch", help="start the activity on the tablet by name")
    la.add_argument("serial", help="device serial (boppo-<SERIAL>.local)")
    la.add_argument("--activity", default="rhythm_game", help="activity package/folder name")
    la.add_argument("--password", default=None, help="bearer password (skip to pair)")
    la.add_argument("--pair", action="store_true", help="force re-pair")
    la.set_defaults(func=_cmd_launch)

    u = sub.add_parser("upload", help="push a built activity + song(s) to a tablet")
    u.add_argument("serial", help="device serial (boppo-<SERIAL>.local)")
    u.add_argument("--wasm", required=True, help="built rhythm_game.wasm")
    u.add_argument("--audio", required=True, nargs="+", help="encoded song file(s)")
    u.add_argument("--activity", default="rhythm_game", help="activity package/folder name")
    u.add_argument("--password", default=None, help="bearer password (skip to pair)")
    u.add_argument("--pair", action="store_true", help="force re-pair even if password given")
    u.set_defaults(func=_cmd_upload)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
