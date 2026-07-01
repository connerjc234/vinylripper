"""Needle-down detection with noise-floor calibration.

Detects when a turntable stylus makes contact with the record by
monitoring the audio input signal against a calibrated noise floor.
"""

from __future__ import annotations

import numpy as np

DEFAULT_CALIBRATION_DURATION = 5.0
"""Default calibration sample length in seconds."""
DEFAULT_THRESHOLD_MULTIPLIER = 3.0
"""Signal must exceed noise floor RMS by this factor to register as 'down'."""
DEFAULT_SILENCE_CONFIRMATION_SECONDS = 5.0
"""Consecutive seconds of silence to confirm needle is up."""
DEFAULT_SILENCE_RATIO = 1.5
"""RMS below noise_floor_rms * this value is considered silence."""


class NeedleDetector:
    """Detects needle state based on audio input signal vs. noise floor.

    Usage:
        detector = NeedleDetector(samplerate=44100)

        # Phase 1: Calibrate (record 5s with needle lifted)
        detector.calibrate(silent_chunk)

        # Phase 2: Detect needle drop
        if detector.is_signal_detected(live_chunk):
            start_recording()

        # Phase 3: Detect needle lift (end of side)
        if detector.is_silence(live_chunk):
            pause_recording()
    """

    def __init__(self, samplerate: int = 44100):
        self.samplerate = samplerate
        self.noise_floor_rms: float = 0.0
        self.noise_floor_peak: float = 0.0
        self.calibrated = False
        self._silence_frames = 0
        self._silence_confirmation_samples: int = int(
            samplerate * DEFAULT_SILENCE_CONFIRMATION_SECONDS
        )

    def calibrate(self, audio_chunk: np.ndarray) -> None:
        """Record a silence sample to establish the noise floor.

        Should be called with ~5 seconds of audio recorded while the
        needle is lifted (no record playing).
        """
        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.mean(axis=1)

        self.noise_floor_rms = float(np.sqrt(np.mean(audio_chunk**2)))
        self.noise_floor_peak = float(np.max(np.abs(audio_chunk)))

        # Guard against zero — if literally zero, set a tiny floor
        if self.noise_floor_rms < 1e-12:
            self.noise_floor_rms = 1e-12
        if self.noise_floor_peak < 1e-12:
            self.noise_floor_peak = 1e-12

        self.calibrated = True
        self._silence_frames = 0

    def is_signal_detected(
        self,
        audio_chunk: np.ndarray,
        threshold_multiplier: float = DEFAULT_THRESHOLD_MULTIPLIER,
    ) -> bool:
        """Return True if audio signal exceeds noise floor (needle is down).

        If not calibrated, returns True (fallback — don't block recording).
        """
        if not self.calibrated:
            return True

        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.mean(axis=1)

        rms = float(np.sqrt(np.mean(audio_chunk**2)))
        self._silence_frames = 0  # Reset silence counter on any signal
        return rms > self.noise_floor_rms * threshold_multiplier

    def is_silence(
        self,
        audio_chunk: np.ndarray,
        silence_ratio: float = DEFAULT_SILENCE_RATIO,
    ) -> bool:
        """Return True if signal is at or below noise floor (needle lifted).

        Requires CONSECUTIVE silence for ``silence_confirmation_seconds``
        to prevent false positives from quiet passages.
        """
        if not self.calibrated:
            return False

        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.mean(axis=1)

        rms = float(np.sqrt(np.mean(audio_chunk**2)))
        threshold = self.noise_floor_rms * silence_ratio

        if rms <= threshold:
            self._silence_frames += len(audio_chunk)
        else:
            self._silence_frames = 0

        return self._silence_frames >= self._silence_confirmation_samples

    @property
    def noise_floor_db(self) -> float:
        """Return noise floor RMS in dBFS (approximate)."""
        if self.noise_floor_rms <= 0:
            return -96.0
        return float(20 * np.log10(self.noise_floor_rms))

    def reset(self) -> None:
        """Clear calibration data and silence counter."""
        self.noise_floor_rms = 0.0
        self.noise_floor_peak = 0.0
        self.calibrated = False
        self._silence_frames = 0
