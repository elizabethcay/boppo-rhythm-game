//! Ties the chart, the five lanes, and scoring together. Pure and host-testable:
//! `tick`/`judge` take an explicit `now_ms`, and `button_colors` returns the
//! color for each of the 10 buttons. `main.rs` drives these from the device.

use crate::chart::Chart;
use crate::lane::{Judgment, Lane, Resolution};
use crate::render::{self, Rgb};
use crate::LANES;

/// One color per physical button, indexed 0..=9 (B0..B9).
pub const BUTTON_COUNT: usize = 10;

pub struct GameState {
    chart: Chart,
    lanes: [Lane; LANES],
    /// Per-lane hit times, ascending (derived from the flat chart at load).
    lane_times: [Vec<u32>; LANES],
    /// Index of each lane's next unresolved note.
    cursor: [usize; LANES],
    score: crate::score::Score,
}

impl GameState {
    pub fn new(chart: Chart) -> Self {
        // Split the flat note list into per-lane time lists once, up front.
        let mut lane_times: [Vec<u32>; LANES] = Default::default();
        for note in chart.notes {
            if (note.lane as usize) < LANES {
                lane_times[note.lane as usize].push(note.hit_time_ms);
            }
        }
        Self {
            chart,
            lanes: [Lane::new(), Lane::new(), Lane::new(), Lane::new(), Lane::new()],
            lane_times,
            cursor: [0; LANES],
            score: crate::score::Score::new(),
        }
    }

    pub fn score(&self) -> &crate::score::Score {
        &self.score
    }

    /// True once every lane has resolved all its notes.
    pub fn chart_complete(&self) -> bool {
        (0..LANES).all(|l| self.cursor[l] >= self.lane_times[l].len())
    }

    /// Advance every lane's clock-driven state to `now_ms`.
    pub fn tick(&mut self, now_ms: u32) {
        let lead = self.chart.lead_time_ms;
        let half = self.chart.half_window_ms();
        for l in 0..LANES {
            let next_hit = self.lane_times[l].get(self.cursor[l]).copied();
            if let Some(Resolution::Miss) = self.lanes[l].advance(now_ms, lead, half, next_hit) {
                self.score.on_miss();
                self.cursor[l] += 1;
            }
        }
    }

    /// Judge a raw button press at `now_ms`. `button_index` is 0..=9.
    pub fn judge(&mut self, button_index: u8, now_ms: u32) {
        let lane = render::lane_for_button(button_index) as usize;
        if lane >= LANES {
            return;
        }
        match self.lanes[lane].press(now_ms) {
            Judgment::Hit => {
                self.score.on_hit();
                self.cursor[lane] += 1;
            }
            Judgment::Early => self.score.on_early(),
            Judgment::Stray => self.score.on_early(),
        }
    }

    /// Color for each of the 10 buttons at `now_ms`. Lanes drive their preview
    /// (top row) and judge (bottom row) buttons; unused buttons stay off.
    pub fn button_colors(&self, now_ms: u32) -> [Rgb; BUTTON_COUNT] {
        let lead = self.chart.lead_time_ms;
        let mut colors = [render::OFF; BUTTON_COUNT];
        for l in 0..LANES {
            let lane = l as u8;
            colors[render::preview_button(lane) as usize] = self.lanes[l].top_color(now_ms, lead);
            colors[render::judge_button(lane) as usize] = self.lanes[l].bottom_color(now_ms);
        }
        colors
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chart::{Chart, Note};
    use crate::render::{judge_button, preview_button, ARMED, HIT, OFF};

    fn one_note_chart() -> Chart {
        Chart {
            bpm: 120,
            lead_time_ms: 500,
            hit_window_ms: 150,
            notes: &[Note { lane: 2, hit_time_ms: 1000 }],
        }
    }

    #[test]
    fn full_note_lifecycle_hit() {
        let mut game = GameState::new(one_note_chart());

        game.tick(500); // spawn preview on lane 2
        assert_ne!(game.button_colors(600)[preview_button(2) as usize], OFF);

        game.tick(950); // arm
        assert_eq!(game.button_colors(950)[judge_button(2) as usize], ARMED);

        game.judge(judge_button(2), 1000); // hit
        assert_eq!(game.score().hits, 1);
        assert_eq!(game.score().combo, 1);
        assert_eq!(game.button_colors(1000)[judge_button(2) as usize], HIT);
        assert!(game.chart_complete());
    }

    #[test]
    fn missed_note_resolves_and_breaks_combo() {
        let mut game = GameState::new(one_note_chart());
        game.tick(500);
        game.tick(950);
        game.tick(1076); // past window -> miss
        assert_eq!(game.score().resolved, 1);
        assert_eq!(game.score().hits, 0);
        assert!(game.chart_complete());
    }

    #[test]
    fn wrong_lane_press_during_armed_is_not_a_hit() {
        // Lane 2 armed; player presses lane 0's judge button -> stray, no hit.
        let mut game = GameState::new(one_note_chart());
        game.tick(500);
        game.tick(950);
        game.judge(judge_button(0), 1000);
        assert_eq!(game.score().hits, 0);
        assert_eq!(game.score().combo, 0);
        // Lane 2's note is still live (not resolved by the wrong-lane press).
        assert!(!game.chart_complete());
    }

    #[test]
    fn chord_lights_two_lanes_at_once() {
        let chart = Chart {
            bpm: 120,
            lead_time_ms: 500,
            hit_window_ms: 150,
            notes: &[
                Note { lane: 1, hit_time_ms: 1000 },
                Note { lane: 3, hit_time_ms: 1000 },
            ],
        };
        let mut game = GameState::new(chart);
        game.tick(600); // both lanes in preview simultaneously
        let colors = game.button_colors(600);
        assert_ne!(colors[preview_button(1) as usize], OFF);
        assert_ne!(colors[preview_button(3) as usize], OFF);
    }
}
