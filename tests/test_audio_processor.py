"""Tests for the audio_processor module (FFmpeg wrapper logic)."""


# These tests verify the FFmpeg wrapper logic where possible.
# Full FFmpeg integration tests require an actual FFmpeg binary.


class TestGetAudioInfoPlaceholder:
    def test_imports(self):
        """The module imports cleanly."""
        import vinylripper.core.audio_processor  # noqa: F401
