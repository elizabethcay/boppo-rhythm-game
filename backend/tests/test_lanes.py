from boppo_chart.chart import LANES
from boppo_chart.lanes import (
    Onset,
    assign_lanes_frequency,
    assign_lanes_round_robin,
    build_notes,
    build_notes_from_beats,
    thin_onsets,
)


def test_round_robin_cycles_lanes():
    onsets = [Onset(time_s=i * 0.5) for i in range(7)]
    assert assign_lanes_round_robin(onsets) == [0, 1, 2, 3, 4, 0, 1]


def test_frequency_strategy_low_left_high_right():
    # Ascending centroids should map monotonically non-decreasing across lanes.
    onsets = [Onset(time_s=i * 0.5, centroid_hz=float(hz))
              for i, hz in enumerate([100, 500, 1000, 2000, 4000, 8000, 12000])]
    lanes = assign_lanes_frequency(onsets)
    assert lanes[0] == 0            # lowest -> leftmost
    assert lanes[-1] == LANES - 1   # highest -> rightmost
    assert lanes == sorted(lanes)   # monotonic in centroid order
    assert all(0 <= l < LANES for l in lanes)


def test_frequency_falls_back_without_centroids():
    onsets = [Onset(time_s=i * 0.5) for i in range(5)]  # no centroid_hz
    assert assign_lanes_frequency(onsets) == [0, 1, 2, 3, 4]


def test_thin_onsets_enforces_min_gap():
    onsets = [Onset(time_s=t) for t in [0.0, 0.02, 0.05, 0.2, 0.205, 0.4]]
    kept = thin_onsets(onsets, min_gap_ms=90.0)
    times = [round(o.time_s, 3) for o in kept]
    assert times == [0.0, 0.2, 0.4]


def test_build_notes_from_beats_stays_on_grid():
    # Beats every 500ms; want ~1000ms spacing -> keep every 2nd beat, on the grid.
    beats = [Onset(time_s=i * 0.5, centroid_hz=1000.0) for i in range(10)]
    notes = build_notes_from_beats(beats, beat_period_ms=500.0, min_gap_ms=1000.0)
    times = [n.hit_time_ms for n in notes]
    assert times == [0, 1000, 2000, 3000, 4000]
    for n in notes:
        n.validate()


def test_build_notes_from_beats_keeps_all_when_gap_small():
    beats = [Onset(time_s=i * 0.5) for i in range(6)]
    notes = build_notes_from_beats(beats, beat_period_ms=500.0, min_gap_ms=400.0)
    assert len(notes) == 6  # step = 1, every beat kept


def test_build_notes_sorted_and_valid():
    onsets = [Onset(time_s=t, centroid_hz=hz)
              for t, hz in [(1.0, 200), (0.5, 8000), (2.0, 1000)]]
    notes = build_notes(onsets, strategy="freq", min_gap_ms=0)
    times = [n.hit_time_ms for n in notes]
    assert times == sorted(times)
    assert times == [500, 1000, 2000]
    for n in notes:
        n.validate()
