"""Onset -> lane assignment.

Pure logic (no audio deps) so it's unit-testable in isolation. The audio stage
(`analysis.py`) produces a list of `Onset`s; this module turns them into notes on
one of the 5 lanes, and thins them so the chart is playable.

Two strategies:

* ``freq`` (default) — map each onset's spectral centroid to a lane, low
  frequencies on the left (lane 0), highs on the right (lane 4). Bins are chosen
  from the actual centroid distribution (quantiles) so the lanes stay balanced
  regardless of the song's absolute frequency range. Musically intuitive: bass
  hits land left, cymbals/leads land right.
* ``round_robin`` — ignore features, cycle 0,1,2,3,4. Even and predictable;
  a good baseline / fallback for percussive tracks with flat spectra.
"""

from __future__ import annotations

from dataclasses import dataclass

from .chart import LANES, Note


@dataclass(frozen=True)
class Onset:
    """One detected onset. `centroid_hz` may be None if not computed."""

    time_s: float
    centroid_hz: float | None = None
    strength: float = 1.0


def _quantile_bins(values: list[float], bins: int) -> list[float]:
    """Return `bins - 1` interior cut points at even quantiles of `values`."""
    if not values:
        return []
    ordered = sorted(values)
    cuts = []
    for i in range(1, bins):
        pos = i / bins * (len(ordered) - 1)
        lo = int(pos)
        frac = pos - lo
        hi = min(lo + 1, len(ordered) - 1)
        cuts.append(ordered[lo] * (1 - frac) + ordered[hi] * frac)
    return cuts


def _lane_from_cuts(value: float, cuts: list[float]) -> int:
    lane = 0
    for cut in cuts:
        if value > cut:
            lane += 1
        else:
            break
    return min(lane, LANES - 1)


def assign_lanes_frequency(onsets: list[Onset]) -> list[int]:
    """Map onsets to lanes by spectral centroid (quantile-binned)."""
    centroids = [o.centroid_hz for o in onsets if o.centroid_hz is not None]
    if not centroids:
        # No spectral info — fall back to round robin.
        return assign_lanes_round_robin(onsets)
    cuts = _quantile_bins(centroids, LANES)
    lanes = []
    for o in onsets:
        if o.centroid_hz is None:
            lanes.append(len(lanes) % LANES)
        else:
            lanes.append(_lane_from_cuts(o.centroid_hz, cuts))
    return lanes


def assign_lanes_round_robin(onsets: list[Onset]) -> list[int]:
    return [i % LANES for i in range(len(onsets))]


STRATEGIES = {
    "freq": assign_lanes_frequency,
    "round_robin": assign_lanes_round_robin,
}


def thin_onsets(onsets: list[Onset], min_gap_ms: float) -> list[Onset]:
    """Drop onsets closer than `min_gap_ms` to the previously kept one.

    Keeps the chart playable on a 10-button device — a human can't hit notes
    microseconds apart. Onsets are assumed sorted by time; the stronger of two
    close onsets is *not* preferred here (we keep the earlier), which keeps the
    rhythm anchored to the first transient.
    """
    if min_gap_ms <= 0:
        return list(onsets)
    kept: list[Onset] = []
    last_ms = None
    for o in onsets:
        t_ms = o.time_s * 1000.0
        if last_ms is None or (t_ms - last_ms) >= min_gap_ms:
            kept.append(o)
            last_ms = t_ms
    return kept


def _notes_from(kept: list[Onset], strategy: str) -> list[Note]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; choose from {sorted(STRATEGIES)}")
    lanes = STRATEGIES[strategy](kept)
    notes = [
        Note(lane=lane, hit_time_ms=round(o.time_s * 1000.0))
        for o, lane in zip(kept, lanes)
    ]
    notes.sort(key=lambda n: n.hit_time_ms)
    return notes


def build_notes(
    onsets: list[Onset],
    strategy: str = "freq",
    min_gap_ms: float = 90.0,
) -> list[Note]:
    """Onset mode: thin onsets by min gap, assign lanes, emit sorted `Note`s.

    Captures busy detail but the survivors can land off the beat — use
    `build_notes_from_beats` for charts that should track the song's pulse.
    """
    ordered = sorted(onsets, key=lambda o: o.time_s)
    thinned = thin_onsets(ordered, min_gap_ms)
    return _notes_from(thinned, strategy)


def _beat_step(beats: list[Onset], beat_period_ms: float, min_gap_ms: float) -> int:
    """How many beats to skip so notes are spaced ~`min_gap_ms` apart, on-grid."""
    if beat_period_ms <= 0 or min_gap_ms <= 0:
        return 1
    return max(1, round(min_gap_ms / beat_period_ms))


def build_notes_from_beats(
    beats: list[Onset],
    beat_period_ms: float,
    strategy: str = "freq",
    min_gap_ms: float = 500.0,
) -> list[Note]:
    """Beat mode: keep every Nth beat (so notes stay on the musical grid), then
    assign lanes. `min_gap_ms` controls density by choosing how many beats to skip.
    """
    ordered = sorted(beats, key=lambda o: o.time_s)
    step = _beat_step(ordered, beat_period_ms, min_gap_ms)
    return _notes_from(ordered[::step], strategy)
