import json

import pytest

from boppo_chart.chart import Chart, Note
from boppo_chart.codegen import SongSpec, songs_to_rust


def sample_chart() -> Chart:
    return Chart(
        song_id="test-song",
        bpm=120,
        lead_time_ms=500,
        hit_window_ms=150,
        notes=[Note(0, 1000), Note(2, 1500), Note(4, 2000)],
    )


def test_roundtrip_json():
    chart = sample_chart()
    restored = Chart.from_json(chart.to_json())
    assert restored.to_dict() == chart.to_dict()


def test_schema_shape():
    data = json.loads(sample_chart().to_json())
    assert set(data) == {"song_id", "bpm", "lead_time_ms", "hit_window_ms", "notes"}
    assert data["notes"][0] == {"lane": 0, "hit_time_ms": 1000}


def test_validate_rejects_bad_lane():
    with pytest.raises(ValueError):
        Note(lane=5, hit_time_ms=0).validate()


def test_validate_rejects_unsorted_notes():
    chart = Chart("x", 120, 500, 150, [Note(0, 2000), Note(0, 1000)])
    with pytest.raises(ValueError):
        chart.validate()


def test_codegen_emits_song_library():
    specs = [
        SongSpec(id="song-a", audio_file="songs/song-a.wav",
                 name_audio="names/song-a.wav", chart=sample_chart()),
        SongSpec(id="song-b", audio_file="songs/song-b.wav",
                 name_audio="names/song-b.wav", chart=sample_chart()),
    ]
    rust = songs_to_rust(specs)
    assert "pub const SONGS: &[Song] = &[" in rust
    # It's an include fragment (dropped into crate::song), so no `use` line.
    assert "use crate::" not in rust
    assert rust.count("Song {") == 2
    assert 'id: "song-a",' in rust
    assert 'audio_file: "songs/song-b.wav",' in rust
    assert 'name_audio: "names/song-a.wav",' in rust
    assert "Note { lane: 0, hit_time_ms: 1000 }," in rust
    assert rust.count("Note {") == 6  # 3 notes x 2 songs
    assert rust.rstrip().endswith("];")
