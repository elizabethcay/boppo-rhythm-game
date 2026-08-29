# Boppo Rhythm Game — Backend (chart pipeline)

Turns a song into a playable chart + a device-format audio file, entirely offline
on a computer. Never runs on the tablet.

```
song(s) in ─▶ onset/beat analysis ─▶ lane assignment ─▶ charts
   (librosa)        │                                    + songs_generated.rs (Rust SONGS)
                    └─▶ re-encode ─▶ songs/<id>.wav|.qoa  (16-bit / 48 kHz / mono)
```
Multiple songs compile into one activity; on the device the player browses the
button menu — press once to hear a song's name, again to play it. See
[Adding your own songs](#adding-your-own-songs) and
[Custom name voices](#custom-name-voices-announce-then-confirm-menu).

## Layout
- `boppo_chart/analysis.py` — onset/beat detection, spectral centroid, BPM (librosa).
- `boppo_chart/lanes.py` — note placement (beat-synced or onset) + lane assignment.
- `boppo_chart/difficulty.py` — easy/normal/hard pacing presets.
- `boppo_chart/chart.py` — `Chart`/`Note` model + JSON (matches the handoff schema).
- `boppo_chart/audio.py` — ffmpeg re-encode to device format (WAV; QOA if `qoaconv` present).
- `boppo_chart/voice.py` — spoken song-name clips (macOS `say`, for the menu).
- `boppo_chart/codegen.py` — songs → `songs_generated.rs` (`SONGS`) for the frontend.
- `boppo_chart/pipeline.py` — ties analysis → assets → compiled activity together.
- `boppo_chart/upload.py` — push `.wasm` + audio to a tablet over its HTTPS API.
- `boppo_chart/cli.py` — `build`, `bundle`, `upload`, `launch` subcommands.

The pure logic (`lanes`, `chart`, `codegen`) has no third-party deps, so its tests
run without the audio stack.

## Setup

librosa's stack needs Python ≤ 3.12 (3.14 is too new for numba). Use 3.11:
```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"        # or: pip install librosa numpy soundfile pytest
```
`ffmpeg` must be on PATH (used for decode/resample/downmix).

## One command: songs → uploadable activity
```bash
.venv/bin/python -m boppo_chart bundle song1.mp3 song2.mp3 --out dist --name library
# add --upload <SERIAL> to push it straight to a tablet
```
`bundle` does everything: analyze each song → charts → encode audio → **compile
the frontend with the whole library baked in** → collect artifacts. Outputs under
`dist/<name>/`:
```
dist/<name>/
├── rhythm_game.wasm        # the activity, with every song's chart compiled in
├── songs_generated.rs      # the Rust SONGS library fragment
├── songs/<id>.wav|.qoa     # one device-format audio per song
└── charts/<id>.chart.json  # portable charts
```
One input works too. Options: `--difficulty easy|normal|hard` (default normal),
`--sync beat|onset` (default beat), `--name-audio ID=PATH` (custom name voices),
`--lanes freq|round_robin`, `--name`, `--format wav|qoa`, `--frontend PATH`,
`--cargo PATH`, `--upload SERIAL`, `--launch`.

### Difficulty
`--difficulty` sets the pacing for young players — same notes on all 5 lanes,
just spaced out and more forgiving. It bundles three knobs:

| Preset | min gap (density) | lead (preview) | window (forgiveness) |
|---|---|---|---|
| easy | 1000 ms (~1 note/s) | 1400 ms | 550 ms |
| normal | 350 ms | 900 ms | 320 ms |
| hard | 140 ms | 550 ms | 170 ms |

Override any single knob with `--min-gap-ms` / `--lead-ms` / `--window-ms`; the
rest still come from the preset. Slower, simpler songs also help a lot.
```bash
.venv/bin/python -m boppo_chart bundle song.mp3 --name kids --difficulty easy --upload <SERIAL>
```

### Note placement (`--sync`)
By default notes snap to the song's **beat grid** (`--sync beat`) so they track the
music. `--sync onset` places them on raw transients instead — busier and can feel
off-beat; usually leave it on `beat`.

## Adding your own songs

Pass any audio files (mp3/wav/flac/m4a/…) to `bundle` — one menu button per song,
filling left→right, top row first (B0, B1, …), capped at 10 songs:
```bash
.venv/bin/python -m boppo_chart bundle golden.mp3 "choosin texas.mp3" \
  --name kids --difficulty easy --upload <SERIAL> --launch
```
Each song's **id** is the slug of its filename (`golden.mp3` → `golden`,
`choosin texas.mp3` → `choosin-texas`). Ids matter for the name-voice mapping
below and for the on-device menu order.

## Custom name voices (announce-then-confirm menu)

On the menu, the **first press** on a song speaks its name; a **second press**
plays it. By default the name is synthesized with macOS `say` (spoken text = the
song id). To use **your own recording — or an AI-generated voice clip** — map an
audio file to a song id with `--name-audio ID=PATH` (repeatable; any audio format,
re-encoded to device format automatically):
```bash
.venv/bin/python -m boppo_chart bundle golden.mp3 "choosin texas.mp3" \
  --name kids --difficulty easy \
  --name-audio "golden=~/Desktop/Golden-name.mp3" \
  --name-audio "choosin-texas=~/Downloads/Choosin-Texas-name.mp3" \
  --upload <SERIAL> --launch
```
- Any song **without** a `--name-audio` falls back to TTS.
- Not sure of an id? Run `build` once and look at the filenames in
  `dist/<name>/charts/` (e.g. `golden.chart.json` → id `golden`).
- Clips are re-encoded to 16-bit/48 kHz/mono like songs, so AI-generated mp3/wav
  files work directly — no manual conversion needed.

### Charts only (no compile)
```bash
.venv/bin/python -m boppo_chart build song1.mp3 song2.mp3 --out dist
```
Same analysis + assets + `songs_generated.rs`, but skips the wasm compile.

## Audio format

Device-native is 16-bit / 48 kHz / mono. **QOA is preferred** for timing-critical
playback (no start/end padding, tiny decode), but needs an external encoder
(`qoaconv` from github.com/phoboslab/qoa — `make qoaconv`, put it on PATH). Until
then `--format wav` works everywhere; the device supports WAV, it's just larger.

## How the library gets compiled in

The device has no runtime filesystem, so every song's chart is compiled into the
wasm. `bundle` automates this without touching the frontend source tree:

1. It writes `songs_generated.rs` (a `SONGS` fragment).
2. It runs `cargo build` with `BOPPO_SONGS_RS=<that file>` set. The frontend's
   `build.rs` reads that env var, includes the fragment into `crate::song`, and
   enables the `have_generated_songs` cfg so `SONGS` becomes the injected library
   (otherwise `SONGS` is the built-in `SAMPLE_SONGS`).
3. It copies the resulting `rhythm_game.wasm` into `dist/<name>/`.

This is the "upload songs = compile an activity" step — still a full Rust build
per bundle (~2.5s here), but now a single command. (The `serde_json` crate is
available on-device, so a future alternative is `include_str!` + runtime parse to
avoid recompiling; not done yet.)

## Upload to a tablet
Usually just add `--upload <SERIAL>` to `bundle`. To upload an existing bundle:
```bash
.venv/bin/python -m boppo_chart upload <SERIAL> \
  --wasm dist/<name>/rhythm_game.wasm \
  --audio dist/<name>/songs/*.wav
```
Pairs first (approve on the device), then pushes the wasm and every song under
`/sd/activities/user/wasm/rhythm_game/` (audio into `songs/`). Both machines must be on
the same LAN.

## Launching on the device
User activities do **not** take one of the built-in arcade menu slots — you start
them by name via the always-available `start` command (no Developer Mode):
```bash
.venv/bin/python -m boppo_chart launch <SERIAL>            # starts rhythm_game
```
Or bundle + upload + launch in one shot:
```bash
.venv/bin/python -m boppo_chart bundle song.mp3 --name mysong --difficulty easy --upload <SERIAL> --launch
```
Reusing a saved `--password <PW>` skips the approval prompt.

## Test
```bash
.venv/bin/python -m pytest
# end-to-end smoke test with synthetic click tracks:
.venv/bin/python scripts/make_click_track.py /tmp/click.wav
.venv/bin/python -m boppo_chart bundle /tmp/click.wav --out dist --name demo
```
