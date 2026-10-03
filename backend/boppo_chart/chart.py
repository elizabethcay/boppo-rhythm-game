"""Chart data model + JSON (de)serialization.

The JSON schema, shared with the frontend's `Chart`/`Note` types:

    {
      "song_id": "string",
      "bpm": 120,
      "lead_time_ms": 500,
      "hit_window_ms": 150,
      "notes": [ { "lane": 0, "hit_time_ms": 1000 }, ... ]
    }

`lane` is 0-4 (left to right). `hit_time_ms` is when the note should be pressed;
the frontend derives `spawn_time_ms = hit_time_ms - lead_time_ms`.

This module has no third-party dependencies so it (and its tests) run without the
audio stack installed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

LANES = 5


@dataclass(frozen=True)
class Note:
    lane: int
    hit_time_ms: int

    def validate(self) -> None:
        if not (0 <= self.lane < LANES):
            raise ValueError(f"lane must be 0..{LANES - 1}, got {self.lane}")
        if self.hit_time_ms < 0:
            raise ValueError(f"hit_time_ms must be >= 0, got {self.hit_time_ms}")


@dataclass
class Chart:
    song_id: str
    bpm: int
    lead_time_ms: int
    hit_window_ms: int
    notes: list[Note]

    def validate(self) -> None:
        if self.bpm <= 0:
            raise ValueError(f"bpm must be > 0, got {self.bpm}")
        if self.lead_time_ms <= 0:
            raise ValueError(f"lead_time_ms must be > 0, got {self.lead_time_ms}")
        if self.hit_window_ms <= 0:
            raise ValueError(f"hit_window_ms must be > 0, got {self.hit_window_ms}")
        for note in self.notes:
            note.validate()
        # Notes must be sorted ascending by hit_time — the frontend assumes it.
        times = [n.hit_time_ms for n in self.notes]
        if times != sorted(times):
            raise ValueError("notes must be sorted ascending by hit_time_ms")

    def to_dict(self) -> dict:
        return {
            "song_id": self.song_id,
            "bpm": self.bpm,
            "lead_time_ms": self.lead_time_ms,
            "hit_window_ms": self.hit_window_ms,
            "notes": [asdict(n) for n in self.notes],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def write_json(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n")

    @classmethod
    def from_dict(cls, data: dict) -> "Chart":
        chart = cls(
            song_id=data["song_id"],
            bpm=int(data["bpm"]),
            lead_time_ms=int(data["lead_time_ms"]),
            hit_window_ms=int(data["hit_window_ms"]),
            notes=[Note(int(n["lane"]), int(n["hit_time_ms"])) for n in data["notes"]],
        )
        chart.validate()
        return chart

    @classmethod
    def from_json(cls, text: str) -> "Chart":
        return cls.from_dict(json.loads(text))
