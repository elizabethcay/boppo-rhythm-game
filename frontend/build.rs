//! Song-library injection.
//!
//! If `BOPPO_SONGS_RS` points at a generated `songs_generated.rs` (from the
//! backend `boppo_chart` pipeline), copy it into `OUT_DIR` and enable the
//! `have_generated_songs` cfg so `song.rs` compiles that library in as `SONGS`.
//! When unset, the activity falls back to `SAMPLE_SONGS`.
//!
//! This keeps the source tree unchanged per build — the library is a build input.

use std::{env, fs, path::PathBuf};

fn main() {
    println!("cargo:rerun-if-env-changed=BOPPO_SONGS_RS");
    println!("cargo:rustc-check-cfg=cfg(have_generated_songs)");

    if let Ok(src) = env::var("BOPPO_SONGS_RS") {
        println!("cargo:rerun-if-changed={src}");
        let content = fs::read_to_string(&src)
            .unwrap_or_else(|e| panic!("BOPPO_SONGS_RS={src}: {e}"));
        let out = PathBuf::from(env::var("OUT_DIR").unwrap()).join("songs_generated.rs");
        fs::write(&out, content).unwrap();
        println!("cargo:rustc-cfg=have_generated_songs");
    }
}
