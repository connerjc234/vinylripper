"""Tests for the Config manager."""

import json
from pathlib import Path

from vinylripper.core.config import (
    Config,
    _get_config_dir,
    _get_default_output_dir,
)


class TestConfigHelpers:
    def test_get_config_dir_not_empty(self):
        """_get_config_dir should return a non-empty path."""
        path = _get_config_dir()
        assert isinstance(path, Path)
        assert len(path.parts) >= 2

    def test_get_default_output_dir_not_empty(self):
        """_get_default_output_dir should return a non-empty string."""
        path = _get_default_output_dir()
        assert isinstance(path, str)
        assert len(path) > 0


class TestConfigFileIO:
    def test_default_config_values(self):
        """Config created without arguments has sensible defaults."""
        c = Config()
        assert c.default_output_format in ("flac", "mp3", "aiff")
        assert 0 <= c.default_flac_compression <= 8
        assert c.silence_threshold_db < 0
        assert c.min_silence_duration > 0

    def test_save_and_load_roundtrip(self, tmp_path):
        """Saving config and reloading it returns the same values."""
        config_path = tmp_path / "vinylripper" / "config.json"
        c1 = Config(config_path=config_path)
        c1.set("discogs_token", "test-token-123")
        c1.set("default_output_format", "mp3")
        assert c1.save() is True

        c2 = Config(config_path=config_path)
        assert c2.discogs_token == "test-token-123"
        assert c2.default_output_format == "mp3"

    def test_validation_passes(self):
        """Default config validates successfully."""
        c = Config()
        valid, msg = c.validate()
        assert valid is True
        assert msg is None

    def test_validation_fails_flac_compression(self):
        """FLAC compression out of 0-8 range fails validation."""
        c = Config()
        c.set("default_flac_compression", 99)
        valid, msg = c.validate()
        assert valid is False
        assert msg is not None

    def test_validation_fails_positive_silence_threshold(self):
        """Silence threshold must be negative dB."""
        c = Config()
        c.set("silence_threshold_db", 10)
        valid, msg = c.validate()
        assert valid is False
        assert msg is not None
        assert "negative" in msg.lower()

    def test_validation_fails_zero_min_silence(self):
        """Min silence duration must be positive."""
        c = Config()
        c.set("min_silence_duration", 0)
        valid, msg = c.validate()
        assert valid is False

    def test_environment_overrides(self, monkeypatch, tmp_path):
        """Environment variables override file config."""
        config_path = tmp_path / "vinylripper" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(json.dumps({"discogs_token": "file-token"}))
        monkeypatch.setenv("VINYLRIPPER_DISCOGS_TOKEN", "env-token")
        monkeypatch.setenv("VINYLRIPPER_OUTPUT_FORMAT", "mp3")

        c = Config(config_path=config_path)
        assert c.discogs_token == "env-token"
        assert c.default_output_format == "mp3"

    def test_env_override_type_conversion(self, monkeypatch, tmp_path):
        """Environment overrides for int/float values are parsed correctly."""
        config_path = tmp_path / "vinylripper" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(json.dumps({}))
        monkeypatch.setenv("VINYLRIPPER_FLAC_COMPRESSION", "5")
        monkeypatch.setenv("VINYLRIPPER_SILENCE_THRESHOLD", "-50")

        c = Config(config_path=config_path)
        assert c.default_flac_compression == 5
        assert isinstance(c.default_flac_compression, int)
        assert c.silence_threshold_db == -50.0
        assert isinstance(c.silence_threshold_db, float)

    def test_last_output_dir(self):
        """last_output_dir setter works correctly."""
        c = Config()
        c.last_output_dir = "/some/path"
        assert c.last_output_dir == "/some/path"
