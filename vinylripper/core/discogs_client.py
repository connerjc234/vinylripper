import re
from typing import Any

import requests

API_BASE = "https://api.discogs.com"
USER_AGENT = "VinylRipper/1.0"

try:
    import discogs_client as _discogs

    HAS_DISCOGS_LIB = True
except ImportError:
    HAS_DISCOGS_LIB = False


class DiscogsSearchResult:
    def __init__(self, data: dict):
        self.id: int = data.get("id", 0)
        self.thumb_url: str = data.get("thumb", "")
        self.cover_url: str = data.get("cover_image", "")
        self.title: str = data.get("title", "")
        self.year: int = data.get("year", 0) or 0
        self.label: str = _join_labels(data.get("label", []))
        self.catno: str = data.get("catno", "")
        self.thumb_data: bytes | None = None

        artist = data.get("artist", "")
        if artist:
            self.artist = artist
            self.release_title = self.title
        elif " - " in self.title:
            parts = self.title.split(" - ", 1)
            self.artist = parts[0]
            self.release_title = parts[1]
        else:
            self.artist = ""
            self.release_title = self.title


def _join_labels(labels):
    names = []
    for label in labels:
        if isinstance(label, dict):
            name = label.get("name", "")
        else:
            name = str(label)
        if name:
            names.append(name)
    return ", ".join(names)


def _parse_track_position(position: str) -> dict[str, Any]:
    """Parse Discogs track position (e.g., 'A1', 'A1.a', 'B2') into components."""
    result = {
        "position": position,
        "side": "",
        "number": 0,
        "sub_track": "",
    }

    if not position:
        return result

    match = re.match(r"^([A-D])(\d+)(?:\.([a-zA-Z]+))?$", position)
    if match:
        result["side"] = match.group(1).upper()
        result["number"] = int(match.group(2))
        if match.group(3):
            result["sub_track"] = match.group(3).lower()

    return result


def _collapse_sub_tracks(tracklist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Collapse sub-tracks (A1.a, A1.b) into single tracks with joined titles.
    This handles medleys and multi-part tracks on vinyl.

    In Discogs, a multi-part track appears as:
    - A1 (main track title)
    - A1.a (part 1)
    - A1.b (part 2)

    This function merges them into a single track entry with the main title
    and sub-tracks as a list for reference.
    """
    if not tracklist:
        return []

    # Group tracks by base position (A1, A2, B1, etc.)
    groups: dict[str, list[dict[str, Any]]] = {}
    for track in tracklist:
        pos = track.get("position", "")
        parsed = _parse_track_position(pos)
        if parsed["side"] and parsed["number"]:
            base_pos = f"{parsed['side']}{parsed['number']}"
        else:
            base_pos = pos
        groups.setdefault(base_pos, []).append(track)

    # Merge each group - sort by side (A, B, C, D) then track number
    def sort_key(pos: str) -> tuple:
        if not pos:
            return (99, 99)
        match = re.match(r"^([A-D])(\d+)", pos.upper())
        if match:
            side = ord(match.group(1)) - ord("A")
            num = int(match.group(2))
            return (side, num)
        return (99, 99)

    collapsed = []
    for base_pos in sorted(groups.keys(), key=sort_key):
        group_tracks = groups[base_pos]
        if len(group_tracks) == 1:
            # Single track, no sub-tracks
            collapsed.append(group_tracks[0])
        else:
            # Multiple tracks with same base position - merge them
            # The first track without sub_track is the main track
            main_track = None
            sub_tracks = []
            for t in group_tracks:
                p = _parse_track_position(t.get("position", ""))
                if p["sub_track"]:
                    sub_tracks.append(t)
                elif main_track is None:
                    main_track = t

            if main_track:
                merged = dict(main_track)
                merged["sub_tracks"] = sub_tracks
                # Join sub-track titles to main title
                if sub_tracks:
                    sub_titles = [
                        st.get("title", "") for st in sub_tracks if st.get("title")
                    ]
                    if sub_titles:
                        merged["title"] = (
                            merged.get("title", "") + " / " + " / ".join(sub_titles)
                        )
                collapsed.append(merged)
            else:
                # No main track, just use first
                collapsed.append(group_tracks[0])

    return collapsed


class DiscogsClient:
    def __init__(self, token: str):
        self.token = token
        self._http = requests.Session()
        self._http.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Authorization": f"Discogs token={token}",
            }
        )
        if HAS_DISCOGS_LIB:
            self._dc = _discogs.Client(USER_AGENT, user_token=token)
        else:
            self._dc = None

    def search(self, query, page=1, per_page=20):
        if self._dc:
            return self._search_dc(query, page, per_page)
        return self._search_requests(query, page, per_page)

    def _search_requests(self, query, page, per_page):
        params = {
            "q": query,
            "page": page,
            "per_page": per_page,
            "type": "release",
        }
        r = self._http.get(f"{API_BASE}/database/search", params=params, timeout=15)
        r.raise_for_status()
        body = r.json()
        results = [DiscogsSearchResult(item) for item in body.get("results", [])]
        self._fetch_thumbs(results)
        return results, body.get("pagination", {})

    def _search_dc(self, query, page, per_page):
        raw = self._dc.search(query, type="release")
        if page > 1:
            try:
                raw.paginator.current_page = page
            except AttributeError:
                pass
        results = []
        for i, item in enumerate(raw):
            if i >= per_page:
                break
            data = {
                "id": item.id,
                "thumb": getattr(item, "thumb", ""),
                "cover_image": getattr(item, "cover_image", ""),
                "title": item.title,
                "year": getattr(item, "year", 0) or 0,
                "label": [],
                "catno": "",
                "artist": "",
            }
            result = DiscogsSearchResult(data)

            try:
                result.artist = ", ".join(a.name for a in item.artists)
            except Exception:
                result.artist = ""
            try:
                result.label = ", ".join(label.name for label in item.labels)
            except Exception:
                result.label = ""
            try:
                result.catno = item.data.get("catno", "")
            except Exception:
                pass

            results.append(result)

        self._fetch_thumbs(results)
        pagination = {
            "page": page,
            "pages": 1,
            "per_page": per_page,
            "items": len(results),
        }
        return results, pagination

    def _fetch_thumbs(self, results):
        for r in results:
            if not r.thumb_url:
                continue
            try:
                resp = self._http.get(r.thumb_url, timeout=5)
                if resp.status_code == 200:
                    r.thumb_data = resp.content
            except Exception:
                pass

    def get_release(self, release_id):
        if self._dc:
            return self._get_release_dc(release_id)
        return self._get_release_requests(release_id)

    def _get_release_requests(self, release_id):
        r = self._http.get(f"{API_BASE}/releases/{release_id}", timeout=15)
        r.raise_for_status()
        return r.json()

    def _get_release_dc(self, release_id):
        rel = self._dc.release(release_id)

        tracklist = []
        for t in getattr(rel, "tracklist", []):
            track_data = {
                "position": getattr(t, "position", ""),
                "title": getattr(t, "title", ""),
                "duration": getattr(t, "duration", ""),
            }
            try:
                track_data["artist"] = ", ".join(a.name for a in t.artists)
            except Exception:
                track_data["artist"] = ""
            tracklist.append(track_data)

        tracklist = _collapse_sub_tracks(tracklist)

        return {
            "id": rel.id,
            "title": rel.title,
            "year": getattr(rel, "year", 0) or 0,
            "artists": [{"name": a.name} for a in getattr(rel, "artists", [])],
            "labels": [
                {"name": label.name, "catno": getattr(label, "catno", "")}
                for label in getattr(rel, "labels", [])
            ],
            "genres": getattr(rel, "genres", []),
            "styles": getattr(rel, "styles", []),
            "tracklist": tracklist,
            "images": [
                {
                    "uri": img.get("uri", ""),
                    "uri150": img.get("uri150", ""),
                    "type": img.get("type", ""),
                }
                for img in getattr(rel, "images", [])
            ],
        }

    def fetch_cover(self, cover_url: str) -> tuple[bytes | None, str]:
        if not cover_url:
            return None, "image/jpeg"
        try:
            resp = self._http.get(cover_url, timeout=10)
            if resp.status_code == 200:
                ct = resp.headers.get("Content-Type", "image/jpeg")
                return resp.content, ct
        except Exception:
            pass
        return None, "image/jpeg"
