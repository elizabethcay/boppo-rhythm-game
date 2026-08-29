//! Boppo rhythm-game activity entry point (device / wasm only).
//!
//! Flow, restarted each time `activity` returns (the runtime clears lights and
//! stops audio between runs, which is exactly "return to the menu"):
//!
//!   menu (pick a song)  ->  play (the chart)  ->  results  ->  return
//!
//! All decisions live in the `rhythm_game` library; this file is I/O: the button
//! grid, the `Instant` clock, and LED flushes. It builds only for wasm32-wasip1.

// Audio-timing calibration (ms). now_ms = elapsed - AUDIO_OFFSET_MS, so a note at
// hit_time becomes due when elapsed = hit_time + AUDIO_OFFSET_MS:
//   negative -> notes fire EARLIER (use when notes feel late vs the music)
//   positive -> notes fire later
// Tuned on real hardware; expose on a calibration screen later.
#[cfg(target_arch = "wasm32")]
const AUDIO_OFFSET_MS: i64 = -120;

#[cfg(target_arch = "wasm32")]
mod activity {
    use super::AUDIO_OFFSET_MS;
    use boppo_wasm::{audio, color, Button, ButtonEvents, Framebuffer};
    use rhythm_game::game::GameState;
    use rhythm_game::render::{self, Rgb};
    use rhythm_game::song::{Song, SONGS};
    use rhythm_game::FRAME_MS;
    use std::time::Instant;

    pub fn run() {
        boppo_wasm::init_and_run_async(activity);
    }

    async fn activity(_num_starts: u32) {
        let mut events = ButtonEvents::subscribe();

        let selected = select_song(&mut events).await;
        let song = &SONGS[selected];

        ready_countdown().await;
        play_song(song, &mut events).await;
        // Returning restarts the activity -> back to the menu.
    }

    /// A traffic-light "get ready" so gameplay doesn't start abruptly: flash the
    /// whole grid red, off, orange, off, green, off — then the song begins.
    async fn ready_countdown() {
        const ON_MS: u64 = 600;
        const OFF_MS: u64 = 300;
        let red: Rgb = (255, 0, 0);
        let orange: Rgb = (255, 140, 0);
        let green: Rgb = (0, 220, 60);

        for color in [red, orange, green] {
            flush_colors(&[color; 10]);
            boppo_wasm::executor::sleep_ms(ON_MS).await;
            flush_colors(&[render::OFF; 10]);
            boppo_wasm::executor::sleep_ms(OFF_MS).await;
        }
    }

    /// Announce-then-confirm song select. The first press on a song speaks its
    /// name and highlights it; a second press on that same song plays it; a press
    /// on a different song announces that one instead. Returns the chosen index.
    async fn select_song(events: &mut ButtonEvents) -> usize {
        let num = SONGS.len().min(render::MENU_PALETTE.len());
        let mut focused: Option<usize> = None;
        flush_colors(&render::menu_colors_focused(num, focused));

        loop {
            let event = events.next().await;
            if !event.is_pressed() {
                continue;
            }
            let idx = event.button().index();
            if idx >= num {
                continue;
            }

            if focused == Some(idx) {
                audio::stop_all();
                return idx;
            }

            focused = Some(idx);
            audio::stop_all();
            audio::play(SONGS[idx].name_audio);
            flush_colors(&render::menu_colors_focused(num, focused));
        }
    }

    /// Run one song: start audio, then tick + judge + render each frame until the
    /// song finishes, then show the results.
    async fn play_song(song: &Song, events: &mut ButtonEvents) {
        let mut game = GameState::new(song.chart);

        let controller = audio::play_with_controller(song.audio_file);
        let start = Instant::now();
        // Discard presses made during the countdown so they aren't judged at t=0.
        while events.try_next().is_some() {}

        loop {
            while let Some(event) = events.try_next() {
                if event.is_pressed() {
                    let now = now_ms(start);
                    game.judge(event.button().index() as u8, now);
                }
            }

            let now = now_ms(start);
            game.tick(now);
            flush_frame(&game, now);

            if controller.is_finished() {
                break;
            }
            boppo_wasm::executor::sleep_ms(FRAME_MS as u64).await;
        }

        show_results(&game).await;
    }

    /// Milliseconds on the audio timeline, corrected by the calibration offset.
    fn now_ms(start: Instant) -> u32 {
        let elapsed = start.elapsed().as_millis() as i64;
        (elapsed - AUDIO_OFFSET_MS).max(0) as u32
    }

    fn to_rgb(c: Rgb) -> color::RGB {
        color::RGB::new(c.0, c.1, c.2)
    }

    /// Push a 10-button color array in one flush.
    fn flush_colors(colors: &[Rgb; 10]) {
        let mut fb = Framebuffer::new();
        for (idx, &c) in colors.iter().enumerate() {
            fb.set_color(Button::from_index(idx), to_rgb(c));
        }
        fb.flush();
    }

    /// Compose and flush one gameplay frame.
    fn flush_frame(game: &GameState, now: u32) {
        flush_colors(&game.button_colors(now));
    }

    /// Placeholder results screen: light the bottom row green/red by accuracy for
    /// a moment so the run visibly ends. TODO: real accuracy / max-combo display.
    async fn show_results(game: &GameState) {
        let s = game.score();
        let c = if s.accuracy() >= 0.5 { color::GREEN } else { color::RED };
        let mut fb = Framebuffer::new();
        for col in 0..5u8 {
            fb.set_color(Button::from_index(5 + col as usize), c);
        }
        fb.flush();
        boppo_wasm::executor::sleep_ms(3000).await;
    }
}

fn main() {
    #[cfg(target_arch = "wasm32")]
    activity::run();
    // On the host target this binary does nothing; the logic is exercised by the
    // library's unit tests (`cargo test`).
}
