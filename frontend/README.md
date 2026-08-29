# Boppo Rhythm Game — Frontend (Rust → WASM)

The on-device activity: game loop, LED rendering, input judging, scoring. Built on
the official [`boppo_wasm`](https://crates.io/crates/boppo_wasm) crate.

## Architecture

Two layers, split by testability:

- **`src/lib.rs` (library) — device-independent game logic.** No `boppo_wasm`
  dependency, so `cargo test` runs it on the host. Holds the per-lane state
  machine, judging, scoring, the chart model, and frame composition.
- **`src/main.rs` (binary) — the async device shell.** Built on `boppo_wasm`,
  compiled only for `wasm32-wasip1`. Subscribes to button events, drives the
  clock, ticks the game, flushes LEDs. Pure I/O — all decisions are in the lib.

### Activity flow (`main.rs`)
`init_and_run_async` re-runs the activity each time it returns, which is exactly
"back to the menu":

    menu (announce → confirm)  →  countdown  →  play (the chart)  →  results  →  return

- **Menu** — one lit button per song, distinct hue, capped at the 10 buttons.
  It's *announce-then-confirm*: the first press on a song speaks its name clip and
  highlights it (others dim); a second press on that song plays it; pressing a
  different song announces that one instead.
- **Countdown** — the whole grid flashes red → orange → green ("get ready") so
  gameplay doesn't start abruptly; presses during it are discarded.
- **Play / results** — the chart runs, then the bottom row flashes green/red by
  accuracy before returning to the menu.

### Module map (lib)
- `song.rs` — `Song { id, name_audio, audio_file, chart }` + the compiled-in `SONGS`.
- `lane.rs` — per-lane state machine (Idle → Preview → Armed → resolved). Preview
  and early-click feedback are independent tracks; input never cancels a preview.
- `game.rs` — `GameState`: `tick(now_ms)`, `judge(button, now_ms)`,
  `button_colors(now_ms) -> [Rgb; 10]`. Pure and fully unit-tested.
- `chart.rs` — `Chart`/`Note`; chart data is a compiled-in `&[Note]` const.
- `render.rs` — colors, brightness interpolation, `menu_colors`, lane ↔ button mapping.
- `score.rs` — combo / accuracy tracking (placeholder point values).

## Timing (the handoff's headline risk — resolved)

The handoff worried that reconstructing the audio clock by accumulating
`boppo_poll` timeouts would drift, because `boppo_poll` returns early on input and
reports no elapsed time. **That risk does not apply here.** `boppo_wasm`'s
embassy-time driver defines `now()` as `std::time::Instant::now().elapsed()` —
i.e. `std::time::Instant` works on the device. `main.rs` reads the clock fresh
from `Instant` every frame and passes `now_ms` into `GameState`, so frame-pacing
jitter never affects judging. A fixed `AUDIO_OFFSET_MS` in `main.rs` corrects for
audio-start latency (wire it to a calibration screen later).

## Verified platform facts (developer.boppo.com + crate sources, 2026-08-24)
- WASM stack **32 KB** — no recursion, no large stack arrays. (Binary *size* is a
  separate budget; the 103 KB artifact is fine.)
- WASIp1 **filesystem APIs unavailable** → charts compiled in, not read from disk.
- Lights are **Button-ordered** (B0..B9), 4 per button (top/left/right/bottom);
  `boppo_core` owns the button→light mapping via `Framebuffer::set_color(Button, …)`.
- Buttons: all 10 emit press/release events (B0–B4 top row, **B5–B9 bottom row**).
- Audio: device is **16-bit / 48 kHz / mono**. Ship **QOA** (no start/end padding,
  tiny decode cost) for timing-critical playback — `audio::play("song.qoa")`.
  Files resolve relative to the activity folder. This **corrects** the handoff's
  "use WAV" note.
- Host import module is `"host"` (only relevant if you ever drop to raw FFI).

## Build & test

Host-side unit tests (no device / wasm target needed):
```bash
cargo test
```

Device build (plays the built-in `SAMPLE_SONGS`):
```bash
rustup target add wasm32-wasip1
cargo build --release --target wasm32-wasip1
# -> target/wasm32-wasip1/release/rhythm_game.wasm
```

### Song-library injection
`build.rs` reads `BOPPO_SONGS_RS` (a path to a backend-generated
`songs_generated.rs`) and compiles that library in as `SONGS`; unset, the
activity uses `SAMPLE_SONGS`. The backend `bundle` command sets this for you, so
you normally never invoke it by hand. To check which library is baked in:
```bash
BOPPO_SONGS_RS=path/to/songs_generated.rs cargo run --example dump_songs
```

## Not done yet (scaffold TODOs)
- **Menu polish** — the song-select menu is functional (one song per button) but
  minimal: no song labels/scrolling, so it caps at 10 songs, and there's no
  "back out of a song" control mid-play.
- Real **results screen** (current one just flashes the bottom row for 3s).
- **Calibration screen** to set `AUDIO_OFFSET_MS`.
- Backend codegen emits the per-song `Chart` const (replaces `SAMPLE_CHART`) and
  the matching `song.qoa` asset in the activity folder.
- Drop a real `song.qoa` into the activity folder before uploading, or `play`
  will fail at runtime.
