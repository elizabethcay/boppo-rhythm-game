//! Colors, brightness interpolation, and lane <-> button mapping.
//!
//! This module stays device-independent: colors are plain `(u8, u8, u8)` tuples
//! and the game composes a per-button color array. `main.rs` converts those to
//! `boppo_core::color::RGB` and lets `boppo_core` own the button->light mapping
//! (Button-ordered, 4 lights each), so there's a single source of truth for the
//! LED layout. The lane<->button helpers below match that layout.

pub type Rgb = (u8, u8, u8);

pub const OFF: Rgb = (0, 0, 0);
/// Preview peak (top row): light peach, scaled toward black during the ramp.
pub const PREVIEW_PEAK: Rgb = (255, 180, 120);

/// Distinct per-button hues for the song-select menu (one song per button).
pub const MENU_PALETTE: [Rgb; 10] = [
    (255, 0, 0),     // red
    (0, 220, 60),    // green
    (0, 120, 255),   // blue
    (255, 200, 0),   // amber
    (255, 0, 180),   // magenta
    (0, 220, 220),   // cyan
    (255, 110, 0),   // orange
    (140, 0, 255),   // violet
    (0, 255, 140),   // spring green
    (255, 60, 120),  // rose
];
/// Armed (bottom, window open): saturated amber.
pub const ARMED: Rgb = (255, 140, 0);
/// Hit flash: green.
pub const HIT: Rgb = (0, 220, 60);
/// Early / Miss flash: red.
pub const MISS: Rgb = (220, 30, 30);

/// button idx -> (row, col)
pub fn button_position(idx: u8) -> (u8, u8) {
    if idx < 5 {
        (0, idx)
    } else {
        (1, idx - 5)
    }
}

/// (row, col) -> button idx. Top row 0..4, bottom row 5..9.
pub fn button_index(row: u8, col: u8) -> u8 {
    if row == 0 {
        col
    } else {
        5 + col
    }
}

/// Which lane a button press belongs to (both rows share a column = lane).
pub fn lane_for_button(idx: u8) -> u8 {
    button_position(idx).1
}

/// Top-row preview button for a lane.
pub fn preview_button(lane: u8) -> u8 {
    button_index(0, lane)
}

/// Bottom-row judge button for a lane.
pub fn judge_button(lane: u8) -> u8 {
    button_index(1, lane)
}

/// How dim non-focused song buttons get once one song is focused.
pub const MENU_DIM: f32 = 0.18;

/// Menu framebuffer with an optional focused song (the one whose name was just
/// announced, armed to play on a second press). The focused button shows full
/// color; when something is focused, the others dim so it stands out. With
/// nothing focused, every song button is at full color.
pub fn menu_colors_focused(num_songs: usize, focused: Option<usize>) -> [Rgb; 10] {
    let mut colors = [OFF; 10];
    for i in 0..num_songs.min(10) {
        let base = MENU_PALETTE[i];
        colors[i] = match focused {
            Some(f) if f == i => base,
            Some(_) => scale_brightness(base, MENU_DIM),
            None => base,
        };
    }
    colors
}

/// Menu framebuffer with no selection: one distinct hue per song, rest off.
pub fn menu_colors(num_songs: usize) -> [Rgb; 10] {
    menu_colors_focused(num_songs, None)
}

/// Linear-interpolate between two colors; `t` in [0.0, 1.0]. Used for the
/// "get ready" ramp before a song starts (device has no native fade).
pub fn lerp(a: Rgb, b: Rgb, t: f32) -> Rgb {
    let t = t.clamp(0.0, 1.0);
    let mix = |x: u8, y: u8| (x as f32 + (y as f32 - x as f32) * t) as u8;
    (mix(a.0, b.0), mix(a.1, b.1), mix(a.2, b.2))
}

/// Scale a color toward black by `progress` in [0.0, 1.0]. Used for the preview
/// fade-in, since the device has no native LED fade (computed per frame).
pub fn scale_brightness(rgb: Rgb, progress: f32) -> Rgb {
    let p = progress.clamp(0.0, 1.0);
    (
        (rgb.0 as f32 * p) as u8,
        (rgb.1 as f32 * p) as u8,
        (rgb.2 as f32 * p) as u8,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lane_button_roundtrip() {
        for lane in 0..5u8 {
            assert_eq!(lane_for_button(preview_button(lane)), lane);
            assert_eq!(lane_for_button(judge_button(lane)), lane);
        }
        assert_eq!(preview_button(3), 3);
        assert_eq!(judge_button(3), 8);
    }

    #[test]
    fn brightness_endpoints() {
        assert_eq!(scale_brightness(PREVIEW_PEAK, 0.0), OFF);
        assert_eq!(scale_brightness(PREVIEW_PEAK, 1.0), PREVIEW_PEAK);
    }

    #[test]
    fn lerp_endpoints_and_midpoint() {
        let red = (200, 0, 0);
        let yellow = (200, 200, 0);
        assert_eq!(lerp(red, yellow, 0.0), red);
        assert_eq!(lerp(red, yellow, 1.0), yellow);
        assert_eq!(lerp(red, yellow, 0.5), (200, 100, 0));
    }

    #[test]
    fn menu_lights_one_button_per_song() {
        let colors = menu_colors(3);
        assert_eq!(colors[0], MENU_PALETTE[0]);
        assert_eq!(colors[2], MENU_PALETTE[2]);
        assert_eq!(colors[3], OFF); // no 4th song
        // Clamps to 10 buttons even if asked for more.
        assert_eq!(menu_colors(99).iter().filter(|&&c| c != OFF).count(), 10);
    }

    #[test]
    fn focus_highlights_one_and_dims_the_rest() {
        let colors = menu_colors_focused(4, Some(1));
        assert_eq!(colors[1], MENU_PALETTE[1]); // focused: full
        // Others among the songs are dimmed but not off.
        let dim0 = scale_brightness(MENU_PALETTE[0], MENU_DIM);
        assert_eq!(colors[0], dim0);
        assert_ne!(colors[0], OFF);
        assert_ne!(colors[0], MENU_PALETTE[0]);
        assert_eq!(colors[4], OFF); // beyond the song count
    }
}
