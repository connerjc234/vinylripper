import io
import requests

API_BASE = "https://api.discogs.com"
USER_AGENT = "VinylRipper/0.1"

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
    for l in labels:
        if isinstance(l, dict):
            name = l.get("name", "")
        else:
            name = str(l)
        if name:
            names.append(name)
    return ", ".join(names)


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
        r = self._http.get(f"{API_BASE}/database/search", params=params)
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
                result.label = ", ".join(l.name for l in item.labels)
            except Exception:
                result.label = ""
            try:
                result.catno = item.data.get("catno", "")
            except Exception:
                pass

            results.append(result)

        self._fetch_thumbs(results)
        pagination = {"page": page, "pages": 1, "per_page": per_page, "items": len(results)}
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
        r = self._http.get(f"{API_BASE}/releases/{release_id}")
        r.raise_for_status()
        return r.json()

    def _get_release_dc(self, release_id):
        rel = self._dc.release(release_id)
        return {
            "id": rel.id,
            "title": rel.title,
            "year": getattr(rel, "year", 0) or 0,
            "artists": [{"name": a.name} for a in getattr(rel, "artists", [])],
            "labels": [{"name": l.name, "catno": ""} for l in getattr(rel, "labels", [])],
            "genres": getattr(rel, "genres", []),
            "styles": getattr(rel, "styles", []),
            "tracklist": [
                {
                    "position": getattr(t, "position", ""),
                    "title": getattr(t, "title", ""),
                    "duration": getattr(t, "duration", ""),
                }
                for t in getattr(rel, "tracklist", [])
            ],
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
