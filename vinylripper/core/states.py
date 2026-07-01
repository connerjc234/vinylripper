"""Recording state machine and session management for VinylRipper."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import numpy as np

from vinylripper.core.markers import Marker
from vinylripper.core.metadata import AlbumMetadata


class RecordingState(Enum):
    """Formal state machine for recording workflow."""

    IDLE = auto()
    """No recording in progress. App is ready."""
    CALIBRATING = auto()
    """Needle-down calibration in progress (recording noise floor)."""
    CALIBRATED = auto()
    """Calibration complete, waiting for needle drop to start recording."""
    RECORDING = auto()
    """Actively recording audio from input device."""
    PAUSED = auto()
    """Recording paused (needle up detected, side finished)."""
    FLIP_COUNTDOWN = auto()
    """Countdown timer active for record flip."""
    STOPPED = auto()
    """Recording complete, audio available for review/export."""
    PROCESSING = auto()
    """Exporting/splitting tracks."""

    def is_active(self) -> bool:
        """Return True if recording hardware is capturing."""
        return self in (
            RecordingState.RECORDING,
            RecordingState.CALIBRATING,
        )

    def is_live(self) -> bool:
        """Return True if audio may be flowing (warnings may be live)."""
        return self in (
            RecordingState.CALIBRATING,
            RecordingState.RECORDING,
            RecordingState.PAUSED,
            RecordingState.FLIP_COUNTDOWN,
        )


@dataclass
class RecordingSession:
    """Single source of truth for all recording state across tabs.

    Every tab reads from and writes to this object. MainWindow coordinates;
    tabs never communicate directly with each other.
    """

    # Core state
    state: RecordingState = RecordingState.IDLE

    # Audio
    recorded_data: np.ndarray | None = None
    samplerate: int = 44100
    channels: int = 2
    temp_wav_path: str | None = None

    # Metadata
    metadata: AlbumMetadata | None = None

    # Split markers
    markers: list[Marker] = field(default_factory=list)

    # Side tracking
    current_side: int = 1
    total_sides: int = 2

    # Needle-down detection
    noise_floor_rms: float = 0.0
    noise_floor_peak: float = 0.0
    calibrated: bool = False

    # Device
    device_id: int | None = None
    device_name: str = ""

    # Export
    output_format: str = "flac"
    flac_compression: int = 8
    mp3_quality: str = "0"
    aiff_quality: str = "16"
    restoration_level: int = 0

    # Side gap handling
    side_gap_mode: str = "keep"
    """One of: 'keep', 'remove', 'insert'."""
    side_gap_duration: float = 2.0
    """Silence to insert between sides in 'insert' mode (seconds)."""

    # Per-side audio accumulation (for multi-side recording)
    _side_chunks: dict[int, list[np.ndarray]] = field(default_factory=dict)

    def side_letter(self) -> str:
        """Return current side as letter (A, B, C, D)."""
        if self.current_side == 1:
            return "A"
        if self.current_side == 2:
            return "B"
        if self.current_side == 3:
            return "C"
        return "D"

    def get_state_summary(self) -> dict[str, Any]:
        """Return a dict summary for status bar / logging."""
        return {
            "state": self.state.name,
            "side": self.side_letter(),
            "calibrated": self.calibrated,
            "noise_floor_rms": self.noise_floor_rms,
            "device": self.device_name,
            "markers": len(self.markers),
            "duration_s": (
                float(len(self.recorded_data) / self.samplerate)
                if self.recorded_data is not None
                else 0.0
            ),
        }

    def accumulate_audio(self, side: int, chunk: np.ndarray) -> None:
        """Accumulate audio chunk for a given side during recording."""
        if side not in self._side_chunks:
            self._side_chunks[side] = []
        self._side_chunks[side].append(chunk)

    def get_side_data(self, side: int) -> np.ndarray | None:
        """Get concatenated audio for a specific side."""
        chunks = self._side_chunks.get(side, [])
        if not chunks:
            return None
        return np.concatenate(chunks)

    def finalize_audio(self) -> np.ndarray | None:
        """Concatenate all side audio chunks with gap handling.

        Uses side_gap_mode:
        - 'keep': join sides directly (no gap)
        - 'remove': trim trailing silence from each side before joining
        - 'insert': insert side_gap_duration seconds of silence between sides
        """
        if not self._side_chunks:
            return None

        sides_data: list[np.ndarray] = []
        for side in sorted(self._side_chunks.keys()):
            chunks = self._side_chunks[side]
            if not chunks:
                continue
            side_audio = np.concatenate(chunks)

            if self.side_gap_mode == "remove" and self.samplerate > 0:
                # Trim trailing silence (below noise floor threshold)
                threshold = 10 ** (-45 / 20)  # -45 dBFS
                if side_audio.ndim > 1:
                    mono = side_audio.mean(axis=1)
                else:
                    mono = side_audio
                # Find last non-silent sample
                abs_vals = np.abs(mono)
                if np.any(abs_vals > threshold):
                    last_idx = np.where(abs_vals > threshold)[0][-1]
                    # +100ms padding to avoid cutting off a decay tail
                    side_audio = side_audio[: last_idx + int(self.samplerate * 0.1)]
                sides_data.append(side_audio)
            else:
                sides_data.append(side_audio)

        if not sides_data:
            return None

        # Insert silence gaps if mode is 'insert'
        if self.side_gap_mode == "insert" and self.samplerate > 0:
            gap_samples = int(self.samplerate * self.side_gap_duration)
            gap: np.ndarray = (
                np.zeros((gap_samples, self.channels), dtype=np.float32)
                if self.channels > 1
                else np.zeros(gap_samples, dtype=np.float32)
            )

            result_parts: list[np.ndarray] = []
            for i, sd in enumerate(sides_data):
                if i > 0:
                    result_parts.append(gap.copy())
                result_parts.append(sd)
            return np.concatenate(result_parts)
        else:
            return np.concatenate(sides_data)

    def clear_side_data(self) -> None:
        """Clear all accumulated side audio."""
        self._side_chunks.clear()

    def reset(self) -> None:
        """Reset session to IDLE state (keeps device and calibration preferences)."""
        self.state = RecordingState.IDLE
        self.recorded_data = None
        self.temp_wav_path = None
        self.metadata = None
        self.markers = []
        self.current_side = 1
        self.clear_side_data()
