# Boppo Rhythm Game

A Japanese-rhythm-game-style activity for the [Boppo](https://boppo.com) — a
screen-free kids' tablet with 10 light-up mechanical buttons (2 rows of 5) and a
speaker. Upload a song and it generates a beat chart: the **top
row** previews notes as they approach, and you press the matching **bottom-row**
button in time with the music.

It's built as two fully decoupled parts:

| | What it is | Runs on |
|---|---|---|
| [`backend/`](backend) | Python pipeline: song → beat analysis → chart → device audio → a compiled multi-song activity, plus upload/launch to the tablet | your computer (offline) |
| [`frontend/`](frontend) | The Rust → WASM activity itself: song-select menu, gameplay, LED rendering, input judging, scoring | the tablet (WASIp1 runtime) |

## How it plays

```
song menu  →  countdown  →  play  →  results  →  (back to menu)
```

- **Menu** — one lit button per song. Press once to **hear the song's name**
  (announce), press again to **play** it. A different button announces that one.
- **Countdown** — the grid flashes red → orange → green ("get ready").
- **Play** — notes fade in on the top row; press the button below in time.
  Green = hit, red = miss.
- **Results** — a quick green/red flash, then back to the menu.

## Quick start

Prerequisites: [Rust](https://rustup.rs) (with the `wasm32-wasip1` target),
Python 3.11, and `ffmpeg` on your PATH.

```bash
# set up the backend
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# turn songs into an activity and put it on your tablet, in one command
.venv/bin/python -m boppo_chart bundle song1.mp3 song2.mp3 \
  --name kids --difficulty easy --upload <SERIAL> --launch
```

`bundle` analyzes each song, compiles a single WASM activity with every chart
baked in, uploads it to the tablet, and launches it. Add your own recorded or
AI-generated **name voices** with `--name-audio`, tune pacing with
`--difficulty easy|normal|hard`, and more — see [`backend/README.md`](backend/README.md).

## More docs

- [`backend/README.md`](backend/README.md) — the chart pipeline: adding songs,
  custom name voices, difficulty, audio format, uploading and launching.
- [`frontend/README.md`](frontend/README.md) — the on-device activity:
  architecture, the menu/gameplay flow, timing, and building for the device.

## Notes

- **No screen** — everything is buttons, LEDs, the speaker, and voice prompts.
- The game logic is device-independent and unit-tested (`cargo test` /
  `pytest`); only thin I/O layers touch the hardware.
- The device has no runtime filesystem, so each song's chart is *compiled into*
  the activity — "uploading a song" means bundling and compiling it in.
