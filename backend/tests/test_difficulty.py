import pytest

from boppo_chart.difficulty import DIFFICULTIES, resolve


def test_presets_progress_easy_to_hard():
    easy, normal, hard = (DIFFICULTIES[n] for n in ("easy", "normal", "hard"))
    # Easier = sparser notes, longer preview, more forgiving window.
    assert easy.min_gap_ms > normal.min_gap_ms > hard.min_gap_ms
    assert easy.lead_ms > normal.lead_ms > hard.lead_ms
    assert easy.window_ms > normal.window_ms > hard.window_ms


def test_resolve_uses_preset():
    assert resolve("easy") == (
        DIFFICULTIES["easy"].min_gap_ms,
        DIFFICULTIES["easy"].lead_ms,
        DIFFICULTIES["easy"].window_ms,
    )


def test_overrides_win_over_preset():
    min_gap, lead, window = resolve("hard", min_gap_ms=999, window_ms=777)
    assert min_gap == 999          # overridden
    assert window == 777           # overridden
    assert lead == DIFFICULTIES["hard"].lead_ms  # untouched -> preset


def test_unknown_difficulty_raises():
    with pytest.raises(ValueError):
        resolve("impossible")
