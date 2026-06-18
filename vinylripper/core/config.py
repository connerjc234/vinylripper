"""
VinylRipper - Configuration Management

Loads settings from JSON config file with fallback to environment variables.
Handles Discogs API credentials, audio processing parameters, and output settings.
"""

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any


def _get_default_output_dir() -> str:
    """Get platform-appropriate default output directory."""
    music = Path.home() / "Music"
    if music.exists():
        return str(music / "VinylRipper")
    return str(Path.home() / "VinylRipper")


def _get_base_path() -> Path:
    """Get base path for config, works with PyInstaller frozen apps."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).parent
    return Path(__file__).parent.parent.parent


def _get_config_dir() -> Path:
    """Get platform-appropriate config directory.

    - Windows: %APPDATA%/VinylRipper
    - Linux:   ~/.config/vinylripper
    - macOS:   ~/Library/Application Support/VinylRipper
    """
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "VinylRipper"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "VinylRipper"
    else:
        return Path.home() / ".config" / "vinylripper"


class Config:
    """Configuration manager for VinylRipper."""

    DEFAULT_CONFIG = {
        "discogs_token": "",
        "discogs_user_agent": "VinylRipper/1.0",
        "default_output_dir": _get_default_output_dir(),
        "default_output_format": "flac",
        "default_flac_compression": 8,
        "default_mp3_quality": "0",
        "default_restoration_level": 0,
        "silence_threshold_db": -40,
        "min_silence_duration": 1.5,
        "min_track_length": 30,
        "window_width": 1000,
        "window_height": 700,
        "last_output_dir": "",
    }

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_dir = _get_config_dir()
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.json"

        self._config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        config = dict(self.DEFAULT_CONFIG)

        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    file_config = json.load(f)
                config.update(file_config)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Failed to load config: {e}")

        env_overrides = {
            "discogs_token": os.getenv("VINYLRIPPER_DISCOGS_TOKEN"),
            "discogs_user_agent": os.getenv("VINYLRIPPER_USER_AGENT"),
            "default_output_dir": os.getenv("VINYLRIPPER_OUTPUT_DIR"),
            "default_output_format": os.getenv("VINYLRIPPER_OUTPUT_FORMAT"),
            "default_flac_compression": os.getenv("VINYLRIPPER_FLAC_COMPRESSION"),
            "default_mp3_quality": os.getenv("VINYLRIPPER_MP3_QUALITY"),
            "default_restoration_level": os.getenv("VINYLRIPPER_RESTORATION_LEVEL"),
            "silence_threshold_db": os.getenv("VINYLRIPPER_SILENCE_THRESHOLD"),
            "min_silence_duration": os.getenv("VINYLRIPPER_MIN_SILENCE"),
            "min_track_length": os.getenv("VINYLRIPPER_MIN_TRACK_LENGTH"),
        }

        for key, value in env_overrides.items():
            if value is not None:
                if key in ("default_flac_compression", "default_restoration_level"):
                    config[key] = int(value)
                elif key in (
                    "silence_threshold_db",
                    "min_silence_duration",
                    "min_track_length",
                ):
                    config[key] = float(value)
                else:
                    config[key] = value

        return config

    def save(self) -> bool:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w") as f:
                json.dump(self._config, f, indent=2)
            return True
        except OSError as e:
            print(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def update(self, values: dict[str, Any]) -> None:
        self._config.update(values)

    @property
    def discogs_token(self) -> str:
        return self._config.get("discogs_token", "")  # type: ignore[no-any-return]

    @discogs_token.setter
    def discogs_token(self, value: str) -> None:
        self._config["discogs_token"] = value

    @property
    def discogs_user_agent(self) -> str:
        return self._config.get("discogs_user_agent", "VinylRipper/1.0")  # type: ignore[no-any-return]

    @property
    def default_output_dir(self) -> str:
        return self._config.get("default_output_dir", _get_default_output_dir())  # type: ignore[no-any-return]

    @property
    def default_output_format(self) -> str:
        return self._config.get("default_output_format", "flac")  # type: ignore[no-any-return]

    @property
    def default_flac_compression(self) -> int:
        return self._config.get("default_flac_compression", 8)  # type: ignore[no-any-return]

    @property
    def default_mp3_quality(self) -> str:
        return self._config.get("default_mp3_quality", "0")  # type: ignore[no-any-return]

    @property
    def default_restoration_level(self) -> int:
        return self._config.get("default_restoration_level", 0)  # type: ignore[no-any-return]

    @property
    def silence_threshold_db(self) -> float:
        return self._config.get("silence_threshold_db", -40.0)  # type: ignore[no-any-return]

    @property
    def min_silence_duration(self) -> float:
        return self._config.get("min_silence_duration", 1.5)  # type: ignore[no-any-return]

    @property
    def min_track_length(self) -> float:
        return self._config.get("min_track_length", 30.0)  # type: ignore[no-any-return]

    @property
    def window_width(self) -> int:
        return self._config.get("window_width", 1000)  # type: ignore[no-any-return]

    @property
    def window_height(self) -> int:
        return self._config.get("window_height", 700)  # type: ignore[no-any-return]

    @property
    def last_output_dir(self) -> str:
        return self._config.get("last_output_dir", "")  # type: ignore[no-any-return]

    @last_output_dir.setter
    def last_output_dir(self, value: str) -> None:
        self._config["last_output_dir"] = value

    def validate(self) -> tuple[bool, str | None]:
        if self.default_flac_compression < 0 or self.default_flac_compression > 8:
            return False, "FLAC compression level must be between 0 and 8"
        if self.silence_threshold_db > 0:
            return False, "Silence threshold should be negative (dB)"
        if self.min_silence_duration <= 0:
            return False, "Minimum silence duration must be positive"
        if self.min_track_length <= 0:
            return False, "Minimum track length must be positive"
        return True, None

    def __repr__(self) -> str:
        token = self.discogs_token
        return (
            f"Config(\n"
            f"  discogs_token={'*' * len(token) if token else 'NOT SET'},\n"
            f"  output_dir={self.default_output_dir},\n"
            f"  output_format={self.default_output_format},\n"
            f"  silence_threshold={self.silence_threshold_db}dB,\n"
            f"  min_silence_duration={self.min_silence_duration}s,\n"
            f"  min_track_length={self.min_track_length}s,\n"
            f"  flac_compression={self.default_flac_compression},\n"
            f"  restoration_level={self.default_restoration_level}\n"
            f")"
        )


_config_instance: Config | None = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def load_config() -> dict[str, Any]:
    return get_config()._config


def save_config(config: dict[str, Any]) -> bool:
    cfg = get_config()
    cfg.update(config)
    return cfg.save()
