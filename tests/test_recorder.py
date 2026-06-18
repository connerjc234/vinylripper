"""Tests for the Recorder class (audio capture interface)."""


class TestRecorderImports:
    def test_recorder_module_imports(self):
        """The recorder module imports cleanly."""
        import vinylripper.core.recorder  # noqa: F401

    def test_recorder_class_instantiation(self):
        """Recorder can be instantiated with default params."""
        from vinylripper.core.recorder import Recorder

        r = Recorder()
        assert r.samplerate == 44100
        assert r.channels == 2
        assert r.is_recording is False
        assert r.is_paused is False
