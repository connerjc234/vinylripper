"""Tests for the Discogs client logic (parsing, position handling)."""

from vinylripper.core.discogs_client import (
    DiscogsSearchResult,
    _collapse_sub_tracks,
    _parse_track_position,
)


class TestParseTrackPosition:
    def test_empty_position(self):
        """Empty string returns empty result."""
        result = _parse_track_position("")
        assert result["position"] == ""
        assert result["side"] == ""

    def test_standard_vinyl_position(self):
        """A1, B2, C3 etc. parse correctly."""
        result = _parse_track_position("A1")
        assert result["side"] == "A"
        assert result["number"] == 1
        assert result["sub_track"] == ""

        result = _parse_track_position("B2")
        assert result["side"] == "B"
        assert result["number"] == 2

    def test_sub_track_position(self):
        """A1.a, B2.b sub-tracks parse correctly."""
        result = _parse_track_position("A1.a")
        assert result["side"] == "A"
        assert result["number"] == 1
        assert result["sub_track"] == "a"

    def test_invalid_position(self):
        """Non-standard positions still return base result."""
        result = _parse_track_position("Matrix")
        assert result["side"] == ""


class TestCollapseSubTracks:
    def test_empty_tracklist(self):
        """Empty tracklist returns []."""
        assert _collapse_sub_tracks([]) == []

    def test_single_tracks_no_collapse(self):
        """Tracks without sub-tracks pass through unchanged."""
        tracks = [
            {"position": "A1", "title": "Song One"},
            {"position": "A2", "title": "Song Two"},
        ]
        result = _collapse_sub_tracks(tracks)
        assert len(result) == 2
        assert result[0]["title"] == "Song One"

    def test_collapses_sub_tracks(self):
        """Sub-tracks A1.a and A1.b are merged into A1's title."""
        tracks = [
            {"position": "A1", "title": "Medley"},
            {"position": "A1.a", "title": "Part 1"},
            {"position": "A1.b", "title": "Part 2"},
            {"position": "A2", "title": "Next Song"},
        ]
        result = _collapse_sub_tracks(tracks)
        assert len(result) == 2
        assert "Medley" in result[0]["title"]
        assert "Part 1" in result[0]["title"]
        assert "Part 2" in result[0]["title"]

    def test_handles_no_main_track(self):
        """If no main track is found, first sub-track is used."""
        tracks = [
            {"position": "A1.a", "title": "Part 1"},
            {"position": "A1.b", "title": "Part 2"},
            {"position": "A2", "title": "Next"},
        ]
        result = _collapse_sub_tracks(tracks)
        assert len(result) == 2


class TestDiscogsSearchResult:
    def test_basic_properties(self):
        """DiscogsSearchResult parses basic fields."""
        data = {
            "id": 123,
            "title": "Artist Name - Album Title",
            "year": 2024,
            "thumb": "https://example.com/thumb.jpg",
        }
        result = DiscogsSearchResult(data)
        assert result.id == 123
        assert result.year == 2024
        assert result.artist == "Artist Name"
        assert result.release_title == "Album Title"

    def test_artist_field_present(self):
        """When artist field is present, it overrides split-from-title."""
        data = {
            "id": 456,
            "title": "Something",
            "artist": "Real Artist",
        }
        result = DiscogsSearchResult(data)
        assert result.artist == "Real Artist"
        assert result.release_title == "Something"
