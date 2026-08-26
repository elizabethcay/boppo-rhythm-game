//! Boppo rhythm-game — device-independent game logic.
//!
//! This library holds everything that can be reasoned about and unit-tested
//! without a device: the per-lane state machine, judging, scoring, the chart
//! model, and frame composition (per-button colors). It has **no dependency on
//! `boppo_wasm`**, so `cargo test` runs it on the host target.
//!
//! The device glue — the async event/audio/LED loop and the audio clock — lives
//! in `main.rs`, built on `boppo_wasm` and compiled only for wasm. Time is read
//! there from `std::time::Instant` (the runtime's monotonic clock, which the
//! boppo_wasm embassy-time driver is itself built on) and passed into
//! [`game::GameState`] as a plain `now_ms`, so the logic never needs a clock.
//!
//! Verified against developer.boppo.com + the boppo_core/boppo_wasm sources
//! (2026-08-24):
//!   * WASM stack is 32 KB — no recursion, no large stack arrays.
//!   * WASIp1 filesystem APIs unavailable -> chart compiled in as a `&[Note]`.
//!   * `std::time::Instant` works on device -> real monotonic clock, no drift.
//!   * Lights are Button-ordered (B0..B9), 4 per button (top/left/right/bottom).

pub mod chart;
pub mod game;
pub mod lane;
pub mod render;
pub mod score;
pub mod song;

/// Nominal frame length / poll cadence in milliseconds (~60 Hz). Only a render
/// cadence — the authoritative time comes from `Instant`, read fresh each frame.
pub const FRAME_MS: u32 = 16;

/// Number of lanes = number of button columns.
pub const LANES: usize = 5;
