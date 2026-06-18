"""Tests for the AlbumMetadata dataclass and vinyl position generation."""

from vinylripper.core.metadata import AlbumMetadata


class TestAlbumMetadata:
    def test_empty_metadata(self):
        """A default AlbumMetadata should have empty/default fields."""
        meta = AlbumMetadata()
        assert meta.artist == ""
        assert meta.title == ""
        assert meta.year == 0
        assert meta.tracklist == []

    def test_get_vinyl_positions_empty(self):
        """get_vinyl_positions on empty tracklist returns []."""
        meta = AlbumMetadata()
        assert meta.get_vinyl_positions() == []

    def test_get_vinyl_positions_increments(self):
        """Tracks without positions get sequential A1, A2, A3... labels."""
        meta = AlbumMetadata(
            tracklist=[
                {"title": "Track 1"},
                {"title": "Track 2"},
                {"title": "Track 3"},
            ]
        )
        positions = meta.get_vinyl_positions()
        assert positions == ["A1", "A2", "A3"]

    def test_get_vinyl_positions_discogs_style(self):
        """Tracks with Discogs-style A1, A2, B1 positions are honored."""
        meta = AlbumMetadata(
            tracklist=[
                {"position": "A1", "title": "Side A Track 1"},
                {"position": "A2", "title": "Side A Track 2"},
                {"position": "B1", "title": "Side B Track 1"},
                {"position": "B2", "title": "Side B Track 2"},
            ]
        )
        positions = meta.get_vinyl_positions()
        assert positions == ["A1", "A2", "B1", "B2"]

    def test_get_vinyl_positions_skips_to_new_side(self):
        """Side transitions (C, D) are handled correctly."""
        meta = AlbumMetadata(
            tracklist=[
                {"position": "C1", "title": "Side C"},
                {"position": "C2", "title": "Side C track 2"},
                {"position": "D1", "title": "Side D"},
            ]
        )
        positions = meta.get_vinyl_positions()
        assert positions == ["C1", "C2", "D1"]

    def test_get_track_metadata_index(self):
        """get_track_metadata returns correct fields for a given index."""
        meta = AlbumMetadata(
            artist="Test Artist",
            title="Test Album",
            year=2024,
            genres=["Rock"],
            tracklist=[
                {"position": "A1", "title": "Song One", "duration": "3:00"},
                {"position": "A2", "title": "Song Two", "duration": "4:00"},
            ],
        )
        track = meta.get_track_metadata(0)
        assert track["position"] == "A1"
        assert track["title"] == "Song One"
        assert track["artist"] == "Test Artist"
        assert track["album"] == "Test Album"
        assert track["year"] == "2024"
        assert track["track_number"] == "1"
        assert track["total_tracks"] == "2"

    def test_get_track_metadata_out_of_range_returns_empty(self):
        """Asking for an index beyond tracklist returns sensible defaults."""
        meta = AlbumMetadata(
            artist="Artist",
            title="Album",
            tracklist=[{"position": "A1", "title": "Song"}],
        )
        track = meta.get_track_metadata(5)
        assert track["position"] == "6"
        assert track["title"] == "Track 6"
        assert track["artist"] == "Artist"


class TestAlbumMetadataCover:
    def test_cover_defaults(self):
        """Default cover_data is None and cover_mime is image/jpeg."""
        meta = AlbumMetadata()
        assert meta.cover_data is None
        assert meta.cover_mime == "image/jpeg"

    def test_cover_with_data(self):
        """Cover data and mime type are stored correctly."""
        meta = AlbumMetadata(cover_data=b"fake-image-bytes", cover_mime="image/png")
        assert meta.cover_data == b"fake-image-bytes"
        assert meta.cover_mime == "image/png"
