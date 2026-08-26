//! The compiled-in song library.
//!
//! Each `Song` bundles a chart with the audio file it plays. The activity shows
//! one song per button on the menu and plays the one the player picks.
//!
//! A build injects the real library via `BOPPO_SONGS_RS` (see build.rs), which
//! defines `SONGS`. With no injection the activity uses `SAMPLE_SONGS` so a plain
//! `cargo build` still runs.

use crate::chart::{Chart, Note, SAMPLE_CHART};

/// One playable song: a chart, the audio it drives, and a spoken-name clip.
pub struct Song {
    /// Stable identifier, also used for menu ordering/debugging.
    pub id: &'static str,
    /// Spoken-name clip, relative to the activity folder, e.g. "names/foo.wav".
    /// Played when the song is first selected on the menu (announce-then-confirm).
    pub name_audio: &'static str,
    /// Audio path relative to the activity folder, e.g. "songs/foo.wav".
    pub audio_file: &'static str,
    pub chart: Chart,
}

/// A second built-in chart so the default build shows a real menu of two.
const SAMPLE_CHART_B: Chart = Chart {
    bpm: 128,
    lead_time_ms: 500,
    hit_window_ms: 150,
    notes: &[
        Note { lane: 4, hit_time_ms: 800 },
        Note { lane: 3, hit_time_ms: 1200 },
        Note { lane: 2, hit_time_ms: 1600 },
        Note { lane: 1, hit_time_ms: 2000 },
        Note { lane: 0, hit_time_ms: 2400 },
    ],
};

/// Built-in library used when no song library is injected at build time.
pub const SAMPLE_SONGS: &[Song] = &[
    Song {
        id: "sample-a",
        name_audio: "names/sample-a.wav",
        audio_file: "songs/sample-a.wav",
        chart: SAMPLE_CHART,
    },
    Song {
        id: "sample-b",
        name_audio: "names/sample-b.wav",
        audio_file: "songs/sample-b.wav",
        chart: SAMPLE_CHART_B,
    },
];

// A build sets BOPPO_SONGS_RS (see build.rs), compiling the generated library in
// here as `SONGS`. Otherwise the activity uses SAMPLE_SONGS.
#[cfg(have_generated_songs)]
include!(concat!(env!("OUT_DIR"), "/songs_generated.rs"));

/// The song library the activity actually presents (injected at build time, or
/// the built-in sample library).
#[cfg(not(have_generated_songs))]
pub const SONGS: &[Song] = SAMPLE_SONGS;

/// Number of songs shown on the menu, capped at the 10 physical buttons.
pub fn menu_len() -> usize {
    SONGS.len().min(crate::game::BUTTON_COUNT)
}
