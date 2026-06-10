from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AlbumMetadata:
    artist: str = ""
    title: str = ""
    year: int = 0
    label: str = ""
    catalog_number: str = ""
    genres: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    tracklist: list = field(default_factory=list)
    cover_data: Optional[bytes] = None
    cover_mime: str = "image/jpeg"
    discogs_id: int = 0
