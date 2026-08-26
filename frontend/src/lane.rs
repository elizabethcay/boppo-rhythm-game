//! Per-lane state machine (handoff section 4).
//!
//! Each of the 5 lanes runs an independent instance — lanes can be in different
//! states at once, which is how chords render. The key correction from the
//! handoff: a premature press does NOT cancel the preview. The preview ramp and
//! the early-click feedback are on independent tracks; only the clock moves a
//! lane from Preview into Armed, never input.
//!
//! So a lane has two layers:
//!   * `phase`  — Idle / Preview / Armed, driven only by the clock.
//!   * `flash`  — a transient bottom-row overlay (hit/miss/early), driven by input
//!                or by a window expiring. An early flash coexists with Preview.

use crate::render::{self, Rgb};

/// How long hit/miss/early flashes stay lit (handoff ~150–200ms).
pub const FLASH_MS: u32 = 150;

/// Clock-driven layer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Phase {
    Idle,
    Preview { hit: u32 },
    Armed { hit: u32 },
}

#[derive(Debug, Clone, Copy)]
struct Flash {
    color: Rgb,
    until_ms: u32,
}

/// Outcome of a button press on this lane, for the caller to score.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Judgment {
    /// Correct-lane press inside the window; the note is resolved.
    Hit,
    /// Press during Preview, before the window opened. Note stays live.
    Early,
    /// Press while Idle (e.g. wrong lane while another is armed). Resolves nothing.
    Stray,
}

/// Automatic (clock-driven) resolution surfaced by [`Lane::advance`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Resolution {
    /// The window expired unpressed — the note is resolved as a miss.
    Miss,
}

pub struct Lane {
    phase: Phase,
    flash: Option<Flash>,
}

impl Lane {
    pub fn new() -> Self {
        Self {
            phase: Phase::Idle,
            flash: None,
        }
    }

    /// True when there's no in-flight note (Idle) — the caller may hand us the
    /// next note's hit time on the following `advance`.
    pub fn is_idle(&self) -> bool {
        matches!(self.phase, Phase::Idle)
    }

    fn set_flash(&mut self, color: Rgb, now: u32) {
        self.flash = Some(Flash {
            color,
            until_ms: now + FLASH_MS,
        });
    }

    /// Clock tick. `next_hit` is the hit time of this lane's next unresolved note
    /// (only consulted while Idle). Returns `Some(Miss)` if a window just expired.
    pub fn advance(
        &mut self,
        now: u32,
        lead_ms: u32,
        half_window_ms: u32,
        next_hit: Option<u32>,
    ) -> Option<Resolution> {
        // Expire a finished flash.
        if let Some(f) = self.flash {
            if now >= f.until_ms {
                self.flash = None;
            }
        }

        match self.phase {
            Phase::Idle => {
                if let Some(hit) = next_hit {
                    if now >= hit.saturating_sub(lead_ms) {
                        self.phase = Phase::Preview { hit };
                    }
                }
                None
            }
            Phase::Preview { hit } => {
                if now >= hit.saturating_sub(half_window_ms) {
                    self.phase = Phase::Armed { hit };
                }
                None
            }
            Phase::Armed { hit } => {
                if now > hit + half_window_ms {
                    // Window closed with no press.
                    self.phase = Phase::Idle;
                    self.set_flash(render::MISS, now);
                    Some(Resolution::Miss)
                } else {
                    None
                }
            }
        }
    }

    /// Judge a press on this lane at `now`.
    pub fn press(&mut self, now: u32) -> Judgment {
        match self.phase {
            Phase::Armed { .. } => {
                // Armed spans exactly the window, so any press here is inside it.
                self.phase = Phase::Idle;
                self.set_flash(render::HIT, now);
                Judgment::Hit
            }
            Phase::Preview { .. } => {
                // Early: flash red but leave the preview ramp untouched.
                self.set_flash(render::MISS, now);
                Judgment::Early
            }
            Phase::Idle => {
                self.set_flash(render::MISS, now);
                Judgment::Stray
            }
        }
    }

    /// Top-row (preview) color for this lane right now.
    pub fn top_color(&self, now: u32, lead_ms: u32) -> Rgb {
        match self.phase {
            Phase::Preview { hit } => {
                let spawn = hit.saturating_sub(lead_ms);
                let progress = if lead_ms == 0 {
                    1.0
                } else {
                    (now.saturating_sub(spawn)) as f32 / lead_ms as f32
                };
                render::scale_brightness(render::PREVIEW_PEAK, progress)
            }
            _ => render::OFF,
        }
    }

    /// Bottom-row (judge) color for this lane right now.
    pub fn bottom_color(&self, now: u32) -> Rgb {
        if let Some(f) = self.flash {
            if now < f.until_ms {
                return f.color;
            }
        }
        if matches!(self.phase, Phase::Armed { .. }) {
            render::ARMED
        } else {
            render::OFF
        }
    }
}

impl Default for Lane {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const LEAD: u32 = 500;
    const HALF: u32 = 75; // 150ms window

    #[test]
    fn idle_to_preview_to_armed_to_miss() {
        let mut lane = Lane::new();
        let hit = 1000;

        // Before spawn: stays idle.
        assert_eq!(lane.advance(400, LEAD, HALF, Some(hit)), None);
        assert!(lane.is_idle());

        // At spawn (hit - lead = 500): preview begins.
        lane.advance(500, LEAD, HALF, Some(hit));
        assert!(!lane.is_idle());
        assert_ne!(lane.top_color(600, LEAD), render::OFF);

        // At arm point (hit - half = 925): armed, top off, bottom amber.
        lane.advance(925, LEAD, HALF, Some(hit));
        assert_eq!(lane.top_color(925, LEAD), render::OFF);
        assert_eq!(lane.bottom_color(925), render::ARMED);

        // Past window close (hit + half = 1075): miss.
        assert_eq!(lane.advance(1076, LEAD, HALF, Some(hit)), Some(Resolution::Miss));
        assert_eq!(lane.bottom_color(1076), render::MISS);
    }

    #[test]
    fn press_in_window_is_a_hit() {
        let mut lane = Lane::new();
        let hit = 1000;
        lane.advance(500, LEAD, HALF, Some(hit)); // preview
        lane.advance(950, LEAD, HALF, Some(hit)); // armed
        assert_eq!(lane.press(1000), Judgment::Hit);
        assert_eq!(lane.bottom_color(1000), render::HIT);
        assert!(lane.is_idle());
    }

    #[test]
    fn early_press_keeps_preview_animating() {
        let mut lane = Lane::new();
        let hit = 1000;
        lane.advance(500, LEAD, HALF, Some(hit)); // preview
        let before = lane.top_color(700, LEAD);
        assert_eq!(lane.press(700), Judgment::Early);
        // Preview still advancing: later frame is brighter, and NOT idle.
        assert!(!lane.is_idle());
        let after = lane.top_color(800, LEAD);
        assert!(after.0 >= before.0);
        // Bottom shows the early (red) flash meanwhile.
        assert_eq!(lane.bottom_color(700), render::MISS);
    }

    #[test]
    fn stray_press_while_idle() {
        let mut lane = Lane::new();
        assert_eq!(lane.press(300), Judgment::Stray);
        assert_eq!(lane.bottom_color(300), render::MISS);
    }
}
