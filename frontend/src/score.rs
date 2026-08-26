//! Scoring + combo tracking. Values are placeholders pending product sign-off
//! (handoff section 6) — kept in one place so they're easy to tune.

/// Points awarded per clean hit.
pub const HIT_POINTS: u32 = 100;

#[derive(Debug, Clone, Copy, Default)]
pub struct Score {
    pub points: u32,
    pub combo: u32,
    pub max_combo: u32,
    /// Notes hit cleanly.
    pub hits: u32,
    /// Notes resolved (hit + missed). Early presses do NOT count here — the note
    /// they were aimed at is still live and gets resolved later.
    pub resolved: u32,
}

impl Score {
    pub fn new() -> Self {
        Self::default()
    }

    /// A note was hit inside its window.
    pub fn on_hit(&mut self) {
        self.points += HIT_POINTS;
        self.combo += 1;
        if self.combo > self.max_combo {
            self.max_combo = self.combo;
        }
        self.hits += 1;
        self.resolved += 1;
    }

    /// A note's window expired unpressed, or a mistimed press resolved it as a miss.
    pub fn on_miss(&mut self) {
        self.combo = 0;
        self.resolved += 1;
    }

    /// A premature press during preview. Breaks combo but resolves no note.
    pub fn on_early(&mut self) {
        self.combo = 0;
    }

    /// Accuracy in [0.0, 1.0]; 1.0 before any notes resolve.
    pub fn accuracy(&self) -> f32 {
        if self.resolved == 0 {
            1.0
        } else {
            self.hits as f32 / self.resolved as f32
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn combo_builds_and_breaks() {
        let mut s = Score::new();
        s.on_hit();
        s.on_hit();
        assert_eq!(s.combo, 2);
        assert_eq!(s.max_combo, 2);
        s.on_miss();
        assert_eq!(s.combo, 0);
        assert_eq!(s.max_combo, 2);
        assert_eq!(s.points, 2 * HIT_POINTS);
    }

    #[test]
    fn early_breaks_combo_without_resolving() {
        let mut s = Score::new();
        s.on_hit();
        s.on_early();
        assert_eq!(s.combo, 0);
        assert_eq!(s.resolved, 1); // only the hit resolved a note
    }

    #[test]
    fn accuracy_math() {
        let mut s = Score::new();
        assert_eq!(s.accuracy(), 1.0);
        s.on_hit();
        s.on_miss();
        assert_eq!(s.accuracy(), 0.5);
    }
}
