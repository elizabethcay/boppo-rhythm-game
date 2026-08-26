"""Difficulty presets — bundles of the three timing knobs that set how playable
a chart is. All presets keep every song's notes across all 5 lanes; difficulty
changes only *pacing*, never *placement*:

* ``min_gap_ms`` — minimum time between notes (higher = sparser, slower).
* ``lead_ms``    — how long a note previews before the press (higher = more warning).
* ``window_ms``  — how forgiving the press timing is (higher = more lenient).

An explicit `--min-gap-ms/--lead-ms/--window-ms` on the CLI overrides the preset.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT = "normal"


@dataclass(frozen=True)
class Difficulty:
    min_gap_ms: float
    lead_ms: int
    window_ms: int


# Ordered easy -> hard. Easy: sparse notes, long preview, generous window — aimed
# at young kids. Hard: dense, short preview, tight window.
DIFFICULTIES: dict[str, Difficulty] = {
    # easy is tuned for young kids: at most ~1 note/sec, a long preview, and a
    # very forgiving window.
    "easy": Difficulty(min_gap_ms=1000, lead_ms=1400, window_ms=550),
    "normal": Difficulty(min_gap_ms=350, lead_ms=900, window_ms=320),
    "hard": Difficulty(min_gap_ms=140, lead_ms=550, window_ms=170),
}


def resolve(
    name: str,
    *,
    min_gap_ms: float | None = None,
    lead_ms: int | None = None,
    window_ms: int | None = None,
) -> tuple[float, int, int]:
    """Return the effective (min_gap_ms, lead_ms, window_ms).

    Starts from the named preset; any non-None argument overrides that field.
    """
    if name not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {name!r}; choose from {list(DIFFICULTIES)}")
    base = DIFFICULTIES[name]
    return (
        base.min_gap_ms if min_gap_ms is None else min_gap_ms,
        base.lead_ms if lead_ms is None else lead_ms,
        base.window_ms if window_ms is None else window_ms,
    )
