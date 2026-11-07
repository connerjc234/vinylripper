"""Tests for the Recorder class (audio capture interface).

These exercise the buffering logic directly through the stream callback, so no
audio device is needed.
"""

from types import SimpleNamespace

import numpy as np

from vinylripper.core.recorder import Recorder


def _block(n, value=0.0, channels=2):
    return np.full((n, channels), value, dtype=np.float32)


def _feed(rec, blocks, overflow=False):
    status = SimpleNamespace(input_overflow=overflow)
    for b in blocks:
        rec._callback(b, len(b), None, status)


class TestRecorderImports:
    def test_recorder_module_imports(self):
        """The recorder module imports cleanly."""
        import vinylripper.core.recorder  # noqa: F401

    def test_recorder_class_instantiation(self):
        """Recorder can be instantiated with default params."""
        r = Recorder()
        assert r.samplerate == 44100
        assert r.channels == 2
        assert r.is_recording is False
        assert r.is_paused is False
        assert r.overflow_count == 0


class TestRecorderBuffering:
    def test_callback_never_drops_audio(self):
        """A UI stall must not lose audio: every block queued is drained."""
        rec = Recorder(samplerate=1000, blocksize=100)
        blocks = [_block(100, i) for i in range(200)]  # far beyond old cap of 16
        _feed(rec, blocks)
        drained = rec.drain()
        assert len(drained) == 200
        assert [b[0, 0] for b in drained] == list(range(200))

    def test_overflow_status_is_counted(self):
        rec = Recorder(samplerate=1000)
        _feed(rec, [_block(10)] * 3)
        _feed(rec, [_block(10)] * 2, overflow=True)
        assert rec.overflow_count == 2

    def test_recent_audio_returns_tail(self):
        rec = Recorder(samplerate=1000)
        _feed(rec, [_block(100, i) for i in range(10)])  # 1 s, values 0..9
        rec.drain()
        recent = rec.get_recent_audio(0.25)  # 250 frames
        assert recent.shape == (250, 2)
        assert recent[0, 0] == 7 and recent[-1, 0] == 9
        # Asking for more than exists returns everything
        assert len(rec.get_recent_audio(5)) == 1000

    def test_history_is_bounded(self):
        """Recorder keeps only its history window, not the whole recording."""
        rec = Recorder(samplerate=1000, history_secs=2)
        for _ in range(50):  # 10 s of audio in 200-frame drains
            _feed(rec, [_block(200)])
            rec.drain()
        assert 2000 <= rec._recent_len < 2000 + 200
        assert len(rec.get_recent_audio(60)) == rec._recent_len

    def test_empty_recent_audio(self):
        assert len(Recorder().get_recent_audio(10)) == 0
