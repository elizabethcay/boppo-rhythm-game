//! Beat chart: what to play and when.
//!
//! Chart data is compiled in as a `&'static [Note]` const rather than parsed at
//! runtime: the device has no filesystem, and a const needs no parser, which
//! keeps the binary small. The backend emits exactly this shape, so the fields
//! are plain and ordered by `hit_time_ms`.

/// One note: press `lane` at `hit_time_ms`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Note {
    /// 0–4, left to right (button column).
    pub lane: u8,
    /// When the note should be pressed, ms from song start.
    pub hit_time_ms: u32,
}

/// Timing + note list for one song.
#[derive(Debug, Clone, Copy)]
pub struct Chart {
    pub bpm: u16,
    /// How long the top-row preview animates before the hit (`spawn = hit - lead`).
    pub lead_time_ms: u32,
    /// Full width of the judge window, centered on `hit_time_ms`.
    pub hit_window_ms: u32,
    /// Notes, assumed sorted ascending by `hit_time_ms`.
    pub notes: &'static [Note],
}

impl Chart {
    /// Half the hit window — the window spans `[hit - half, hit + half]`.
    pub fn half_window_ms(&self) -> u32 {
        self.hit_window_ms / 2
    }

    /// When the preview should start for a note.
    pub fn spawn_time_ms(&self, note: &Note) -> u32 {
        note.hit_time_ms.saturating_sub(self.lead_time_ms)
    }
}

/// A hand-written chart for desktop testing and the default song library. The
/// game code never depends on these specific values; the backend supplies real
/// charts as a compiled-in `SONGS` list (see `song.rs`).
pub const SAMPLE_CHART: Chart = Chart {
    bpm: 120,
    lead_time_ms: 500,
    hit_window_ms: 150,
    notes: &[
        Note { lane: 0, hit_time_ms: 1000 },
        Note { lane: 2, hit_time_ms: 1500 },
        Note { lane: 4, hit_time_ms: 2000 },
        Note { lane: 1, hit_time_ms: 2500 },
        Note { lane: 3, hit_time_ms: 2500 }, // chord with lane 1
        Note { lane: 0, hit_time_ms: 3000 },
    ],
};
