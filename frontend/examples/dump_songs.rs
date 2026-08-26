//! Prints the song library compiled into the activity, so you can verify a build
//! picked up the injected library:
//!
//!     BOPPO_SONGS_RS=path/to/songs_generated.rs cargo run --example dump_songs
//!
//! With no env set it prints the built-in SAMPLE_SONGS.

use rhythm_game::song::SONGS;

fn main() {
    println!("SONGS ({} in library):", SONGS.len());
    for (i, s) in SONGS.iter().enumerate() {
        println!(
            "  [{i}] {:<16} audio={:<24} bpm={} notes={}",
            s.id,
            s.audio_file,
            s.chart.bpm,
            s.chart.notes.len()
        );
    }
}
