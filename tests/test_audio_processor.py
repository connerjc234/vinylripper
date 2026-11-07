"""Tests for the audio_processor module (FFmpeg wrapper logic)."""

import shutil

import numpy as np
import pytest
import soundfile as sf

from vinylripper.core.audio_processor import (
    build_restoration_filter,
    codec_args,
    convert_audio,
    split_audio_ffmpeg,
)

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg not installed",
)


class TestGetAudioInfoPlaceholder:
    def test_imports(self):
        """The module imports cleanly."""
        import vinylripper.core.audio_processor  # noqa: F401


class TestCodecArgs:
    @pytest.mark.parametrize(
        ("quality", "codec"),
        [("16", "pcm_s16be"), ("24", "pcm_s24be"), ("32f", "pcm_f32be")],
    )
    def test_aiff_bit_depths(self, quality, codec):
        assert codec_args("aiff", aiff_quality=quality) == ["-c:a", codec]

    def test_unknown_aiff_quality_raises(self):
        with pytest.raises(ValueError):
            codec_args("aiff", aiff_quality="8")

    def test_flac_and_mp3(self):
        assert codec_args("flac", flac_compression=5) == [
            "-c:a",
            "flac",
            "-compression_level",
            "5",
        ]
        assert codec_args("mp3", mp3_quality="2") == [
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
        ]


class TestBuildRestorationFilter:
    def _settings(self, hp=False, dc=None, dn=None):
        return {
            "highpass": {"enabled": hp, "cutoff": 40},
            "declick": {"enabled": dc is not None, "strength": dc or 0.0},
            "denoise": {"enabled": dn is not None, "strength": dn or 0.0},
        }

    def test_nothing_enabled(self):
        assert build_restoration_filter(self._settings()) == ""

    def test_uses_highpass_cutoff(self):
        assert build_restoration_filter(self._settings(hp=True)) == "highpass=f=40"

    def test_declick_default_strength_matches_ffmpeg_default(self):
        assert build_restoration_filter(self._settings(dc=0.5)) == "adeclick=t=2.00"

    def test_declick_strength_changes_threshold(self):
        gentle = build_restoration_filter(self._settings(dc=0.1))
        strong = build_restoration_filter(self._settings(dc=0.9))
        t_gentle = float(gentle.split("=")[-1])
        t_strong = float(strong.split("=")[-1])
        # Lower threshold = more aggressive click detection
        assert t_strong < t_gentle
        assert t_strong >= 1.0

    def test_all_filters_chain(self):
        f = build_restoration_filter(self._settings(hp=True, dc=0.5, dn=0.3))
        assert f.split(",")[0] == "highpass=f=40"
        assert f.split(",")[1].startswith("adeclick")
        assert f.split(",")[2].startswith("anlmdn")


def _probe_bits(path):
    """(codec, bit depth) as reported by soundfile."""
    info = sf.info(str(path))
    return info.subtype


@pytest.fixture
def wav24(tmp_path):
    sr = 48000
    t = np.arange(sr * 3) / sr
    x = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path = tmp_path / "in.wav"
    sf.write(path, np.stack([x, x], axis=1), sr, subtype="PCM_24")
    return path


@needs_ffmpeg
class TestExportBitDepth:
    def test_flac_keeps_24_bit(self, wav24, tmp_path):
        out = tmp_path / "out.flac"
        assert convert_audio(str(wav24), str(out), output_format="flac")
        assert _probe_bits(out) == "PCM_24"

    def test_flac_keeps_24_bit_with_restoration(self, wav24, tmp_path):
        out = tmp_path / "out.flac"
        settings = {
            "highpass": {"enabled": True, "cutoff": 30},
            "declick": {"enabled": True, "strength": 0.5},
            "denoise": {"enabled": False, "strength": 0.0},
        }
        assert convert_audio(
            str(wav24), str(out), output_format="flac", restoration_settings=settings
        )
        assert _probe_bits(out) == "PCM_24"

    @pytest.mark.parametrize(
        ("quality", "subtype"),
        [("16", "PCM_16"), ("24", "PCM_24"), ("32f", "FLOAT")],
    )
    def test_aiff_honours_quality(self, wav24, tmp_path, quality, subtype):
        out = tmp_path / "out.aiff"
        assert convert_audio(
            str(wav24), str(out), output_format="aiff", aiff_quality=quality
        )
        assert _probe_bits(out) == subtype

    def test_split_honours_aiff_quality(self, wav24, tmp_path):
        out_dir = tmp_path / "tracks"
        files = split_audio_ffmpeg(
            str(wav24),
            str(out_dir),
            [1.5],
            [{"position": "A1", "title": "One"}, {"position": "A2", "title": "Two"}],
            output_format="aiff",
            aiff_quality="24",
        )
        assert len(files) == 2
        assert all(_probe_bits(f) == "PCM_24" for f in files)
