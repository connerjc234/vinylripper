"""Marker data model for waveform split points.

Replaces flat list[int] with typed markers supporting:
- Normal split markers (track boundaries)
- Locked pairs (joined markers that move together)
- Side gap markers (boundary between record sides)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class MarkerKind(Enum):
    """Type of waveform marker."""

    SPLIT = auto()
    """Normal track boundary. Can be freely dragged."""
    SIDE_GAP = auto()
    """Boundary between sides. Marks side flip location."""
    LOCKED_PAIR = auto()
    """One half of a joined marker pair. Moves with its partner."""


@dataclass
class Marker:
    """A single split point on the waveform."""

    position: int
    """Sample index in the audio data."""

    kind: MarkerKind = MarkerKind.SPLIT
    """Type of this marker."""

    pair_id: int | None = None
    """If part of a LOCKED_PAIR, shared ID tying this marker to its partner.
    None for unpaired markers."""

    label: str = ""
    """Optional display label (e.g. 'A1', 'Side A end', 'B1')."""

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "kind": self.kind.name,
            "pair_id": self.pair_id,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Marker:
        return cls(
            position=d["position"],
            kind=MarkerKind[d["kind"]],
            pair_id=d.get("pair_id"),
            label=d.get("label", ""),
        )


def create_pair(left: Marker, right: Marker, pair_id: int) -> tuple[Marker, Marker]:
    """Join two markers into a locked pair."""
    left.kind = MarkerKind.LOCKED_PAIR
    left.pair_id = pair_id
    right.kind = MarkerKind.LOCKED_PAIR
    right.pair_id = pair_id
    return left, right


def unlink_pair(left: Marker, right: Marker) -> tuple[Marker, Marker]:
    """Break a locked pair back into independent split markers."""
    left.kind = MarkerKind.SPLIT
    left.pair_id = None
    right.kind = MarkerKind.SPLIT
    right.pair_id = None
    return left, right


def markers_from_ints(ints: list[int]) -> list[Marker]:
    """Convert legacy list[int] split points to Marker list."""
    return [Marker(position=p, label=str(i + 1)) for i, p in enumerate(ints)]


def markers_to_ints(markers: list[Marker]) -> list[int]:
    """Extract positions as a flat list (for legacy/split API compatibility)."""
    return sorted([m.position for m in markers])


def clamp_marker(
    marker: Marker,
    min_pos: int,
    max_pos: int,
    min_separation: int = 22050,
    siblings: list[Marker] | None = None,
) -> Marker:
    """Clamp marker position within valid range, respecting minimum separation."""
    pos = marker.position

    # Clamp to absolute bounds
    pos = max(min_pos, min(pos, max_pos))

    # Respect minimum separation from siblings
    if siblings:
        for other in siblings:
            if other is marker:
                continue
            dist = pos - other.position
            if abs(dist) < min_separation:
                # Push away from sibling
                if dist >= 0:
                    pos = other.position + min_separation
                else:
                    pos = other.position - min_separation

    # Re-clamp after sibling adjustments
    pos = max(min_pos, min(pos, max_pos))
    return Marker(position=pos, kind=marker.kind, pair_id=marker.pair_id, label=marker.label)
