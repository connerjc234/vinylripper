import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlbumMetadata:
    artist: str = ""
    title: str = ""
    year: int = 0
    label: str = ""
    catalog_number: str = ""
    genres: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    tracklist: list[dict[str, Any]] = field(default_factory=list)
    cover_data: bytes | None = None
    cover_mime: str = "image/jpeg"
    discogs_id: int = 0

    def get_vinyl_positions(self) -> list[str]:
        """Generate vinyl-style track positions (A1, A2, B1, B2) from tracklist."""
        positions = []
        side = 'A'
        track_num = 1

        for track in self.tracklist:
            pos = track.get("position", "").strip()

            if not pos:
                positions.append(f"{side}{track_num}")
                track_num += 1
                continue

            match = re.match(r'^([A-D])(\d+)', pos.upper())
            if match:
                new_side = match.group(1)
                new_num = int(match.group(2))
                if new_side != side:
                    side = new_side
                    track_num = new_num
                else:
                    track_num = new_num
                positions.append(f"{side}{track_num}")
            else:
                positions.append(f"{side}{track_num}")
                track_num += 1

        return positions

    def get_track_metadata(self, index: int) -> dict[str, Any]:
        """Get metadata for a specific track index with vinyl position."""
        positions = self.get_vinyl_positions()
        track = self.tracklist[index] if index < len(self.tracklist) else {}

        return {
            "position": positions[index] if index < len(positions) else str(index + 1),
            "title": track.get("title", f"Track {index + 1}"),
            "artist": track.get("artist", self.artist),
            "album": self.title,
            "album_artist": self.artist,
            "year": str(self.year) if self.year else "",
            "genre": ", ".join(self.genres) if self.genres else "",
            "track_number": str(index + 1),
            "total_tracks": str(len(self.tracklist)),
            "disc_number": "1",
            "total_discs": "1",
        }
