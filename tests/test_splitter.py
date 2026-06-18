"""Tests for the splitter module (silence detection via numpy)."""

import numpy as np

from vinylripper.core.splitter import (
    _to_mono,
    detect_silence_splits,
    safe_filename,
    split_audio,
)


class TestToMono:
    def test_mono_stays_mono(self):
        """Mono input should be returned unchanged (copy)."""
        audio = np.array([0.1, -0.2, 0.3], dtype=np.float32)
        result = _to_mono(audio)
        np.testing.assert_array_equal(result, audio)
        assert result is not audio  # should be a copy

    def test_stereo_to_mono(self):
        """Stereo (2-channel) input should be averaged to mono."""
        audio = np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32)
        result = _to_mono(audio)
        expected = np.array([0.3, 0.7], dtype=np.float32)
        np.testing.assert_allclose(result, expected)


class TestSafeFilename:
    def test_removes_invalid_chars(self):
        """Invalid filesystem chars are replaced."""
        assert safe_filename("a/b:c*d?") == "abcd"

    def test_collapses_whitespace(self):
        """Multiple spaces are collapsed to one."""
        assert safe_filename("hello    world") == "hello world"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is trimmed."""
        assert safe_filename("  foo  ") == "foo"

    def test_empty_returns_untitled(self):
        """Empty/whitespace-only input returns 'untitled'."""
        assert safe_filename("") == "untitled"
        assert safe_filename("   ") == "untitled"


class TestSplitAudio:
    def test_no_split_points_returns_full(self):
        """With no split points, the full audio is returned as one segment."""
        audio = np.ones(1000, dtype=np.float32)
        segments = split_audio(audio, [])
        assert len(segments) == 1
        assert len(segments[0]) == 1000

    def test_split_at_points(self):
        """Audio is correctly split at given indices."""
        audio = np.arange(100, dtype=np.float32)
        segments = split_audio(audio, [30, 70])
        assert len(segments) == 3
        np.testing.assert_array_equal(segments[0], np.arange(30))
        np.testing.assert_array_equal(segments[1], np.arange(30, 70))
        np.testing.assert_array_equal(segments[2], np.arange(70, 100))

    def test_empty_segments_removed(self):
        """If split points produce empty segments, they are skipped."""
        audio = np.ones(100, dtype=np.float32)
        segments = split_audio(audio, [50, 50])
        assert len(segments) == 2


class TestDetectSilenceSplits:
    def test_too_short_audio_returns_empty(self):
        """Audio shorter than 1 second at 44100 Hz returns []."""
        audio = np.random.randn(100)
        assert detect_silence_splits(audio, 44100) == []

    def test_full_silence_returns_empty(self):
        """Completely silent audio returns empty split list."""
        sr = 44100
        audio = np.zeros(sr * 5, dtype=np.float32)
        splits = detect_silence_splits(audio, sr, threshold_db=-40)
        assert splits == []

    def test_loud_audio_no_silence_returns_empty(self):
        """Audio with no silent regions returns empty split list."""
        sr = 44100
        audio = np.ones(sr * 5, dtype=np.float32) * 0.5
        splits = detect_silence_splits(audio, sr, threshold_db=-40)
        assert splits == []
