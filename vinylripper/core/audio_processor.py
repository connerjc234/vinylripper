"""
VinylRipper - Audio Processing Module

Handles silence detection, track splitting, and audio format conversion using FFmpeg.
Supports FLAC, MP3, and AIFF output formats with professional quality settings.
"""

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger("vinylripper.audio_processor")

_FFMPEG_CACHE = None
_FFPROBE_CACHE = None


class ProcessingCancelled(Exception):
    pass


def _find_ffmpeg() -> str:
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE:
        return _FFMPEG_CACHE

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base_path = Path(meipass)
            for name in ("ffmpeg", "ffmpeg.exe"):
                local_ffmpeg = base_path / name
                if local_ffmpeg.exists():
                    _FFMPEG_CACHE = str(local_ffmpeg)
                    return _FFMPEG_CACHE

    for name in ("ffmpeg", "ffmpeg.exe"):
        path = shutil.which(name)
        if path:
            _FFMPEG_CACHE = path
            return _FFMPEG_CACHE

    raise FileNotFoundError(
        "FFmpeg not found. Please install FFmpeg:\n"
        "  Windows: scoop install ffmpeg  (or download from ffmpeg.org)\n"
        "  macOS:   brew install ffmpeg\n"
        "  Linux:   sudo apt install ffmpeg / sudo dnf install ffmpeg"
    )


def _find_ffprobe() -> str:
    global _FFPROBE_CACHE
    if _FFPROBE_CACHE:
        return _FFPROBE_CACHE

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base_path = Path(meipass)
            for name in ("ffprobe", "ffprobe.exe"):
                local_ffprobe = base_path / name
                if local_ffprobe.exists():
                    _FFPROBE_CACHE = str(local_ffprobe)
                    return _FFPROBE_CACHE

    for name in ("ffprobe", "ffprobe.exe"):
        path = shutil.which(name)
        if path:
            _FFPROBE_CACHE = path
            return _FFPROBE_CACHE

    raise FileNotFoundError(
        "FFprobe not found. Please install FFmpeg (includes ffprobe):\n"
        "  Windows: scoop install ffmpeg  (or download from ffmpeg.org)\n"
        "  macOS:   brew install ffmpeg\n"
        "  Linux:   sudo apt install ffmpeg / sudo dnf install ffmpeg"
    )


def get_audio_info(filepath: str) -> dict[str, Any]:
    """Get audio file info using ffprobe."""
    ffprobe = _find_ffprobe()
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels,duration:format=duration",
        "-of",
        "json",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    import json

    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]
    format_info = data.get("format", {})
    return {
        "sample_rate": int(stream.get("sample_rate", 44100)),
        "channels": int(stream.get("channels", 2)),
        "duration": float(format_info.get("duration", stream.get("duration", 0))),
    }


def detect_silence_ffmpeg(
    filepath: str,
    silence_threshold_db: float = -40,
    min_silence_duration: float = 1.5,
    min_track_length: float = 30,
) -> list[float]:
    """
    Detect silence regions in audio file using FFmpeg's silencedetect filter.
    Returns list of split points in seconds.
    """
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        filepath,
        "-af",
        f"silencedetect=noise={silence_threshold_db}dB:d={min_silence_duration}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    split_points = []
    for line in result.stderr.split("\n"):
        if "silence_start" in line:
            match = re.search(r"silence_start:\s*([\d.]+)", line)
            if match:
                start = float(match.group(1))
                split_points.append(start)

    filtered_points = []
    last_point = -min_track_length
    for point in split_points:
        if point - last_point >= min_track_length:
            filtered_points.append(point)
            last_point = point

    return filtered_points


def split_audio_ffmpeg(
    input_file: str,
    output_dir: str,
    split_points: list[float],
    track_metadata: list[dict[str, Any]],
    output_format: str = "flac",
    flac_compression: int = 8,
    mp3_quality: str = "0",
    aiff_quality: str = "16",
    restoration_level: int = 0,
    restoration_settings: dict | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> list[str]:
    """
    Split audio file at given points and convert to specified format with metadata.
    Returns list of output file paths.

    Args:
        restoration_settings: Dict from CleanupAudioTab.get_settings().
                             Takes precedence over restoration_level when provided.
    """
    ffmpeg = _find_ffmpeg()
    os.makedirs(output_dir, exist_ok=True)

    info = get_audio_info(input_file)
    duration = info["duration"]

    all_points = [0.0] + split_points + [duration]
    output_files = []

    if restoration_settings:
        af_filter_str = build_restoration_filter(restoration_settings)
    else:
        af_filters: list[str] = []
        if restoration_level >= 1:
            af_filters.append("highpass=f=30")
        if restoration_level >= 2:
            af_filters.append("adeclick")
        af_filter_str = ",".join(af_filters) if af_filters else "anull"

    for i in range(len(all_points) - 1):
        if cancel_event and cancel_event.is_set():
            raise ProcessingCancelled("Processing cancelled by user")

        start = all_points[i]
        end = all_points[i + 1]
        track_duration = end - start

        if track_duration < 1.0:
            continue

        meta = track_metadata[i] if i < len(track_metadata) else {}
        position = meta.get("position", str(i + 1))
        title = meta.get("title", f"Track {i + 1}")
        artist = meta.get("artist", "")
        album = meta.get("album", "")
        album_artist = meta.get("album_artist", "")
        year = meta.get("year", "")
        genre = meta.get("genre", "")
        track_number = meta.get("track_number", str(i + 1))
        total_tracks = meta.get("total_tracks", str(len(all_points) - 1))
        disc_number = meta.get("disc_number", "1")
        total_discs = meta.get("total_discs", "1")

        safe_title = re.sub(r'[\\/:*?"<>|]', "", title)
        safe_title = re.sub(r"\s+", " ", safe_title).strip()
        safe_artist = re.sub(r'[\\/:*?"<>|]', "", artist)
        safe_artist = re.sub(r"\s+", " ", safe_artist).strip()

        if safe_artist:
            filename = f"{position} - {safe_artist} - {safe_title}.{output_format}"
        else:
            filename = f"{position} - {safe_title}.{output_format}"

        output_path = os.path.join(output_dir, filename)

        cmd = [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-ss",
            str(start),
            "-t",
            str(track_duration),
            "-i",
            input_file,
        ]

        if af_filter_str != "anull":
            cmd.extend(["-af", af_filter_str])

        if output_format == "flac":
            cmd.extend(["-c:a", "flac", "-compression_level", str(flac_compression)])
        elif output_format == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-q:a", mp3_quality])
        elif output_format == "aiff":
            cmd.extend(["-c:a", "pcm_s16be"])
        else:
            cmd.extend(["-c:a", "flac", "-compression_level", str(flac_compression)])

        metadata_args = []
        if title:
            metadata_args.extend(["-metadata", f"title={title}"])
        if artist:
            metadata_args.extend(["-metadata", f"artist={artist}"])
        if album:
            metadata_args.extend(["-metadata", f"album={album}"])
        if album_artist:
            metadata_args.extend(["-metadata", f"album_artist={album_artist}"])
        if year:
            metadata_args.extend(["-metadata", f"date={year}"])
        if genre:
            metadata_args.extend(["-metadata", f"genre={genre}"])
        if track_number:
            metadata_args.extend(["-metadata", f"track={track_number}"])
        if total_tracks:
            metadata_args.extend(["-metadata", f"tracktotal={total_tracks}"])
        if disc_number:
            metadata_args.extend(["-metadata", f"disc={disc_number}"])
        if total_discs:
            metadata_args.extend(["-metadata", f"disctotal={total_discs}"])

        cmd.extend(metadata_args)
        cmd.append(output_path)

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            stderr = (
                result.stderr.decode("utf-8", errors="replace")
                if isinstance(result.stderr, bytes)
                else str(result.stderr)
            )
            logger.error(f"FFmpeg error for track {i + 1}: {stderr}")
            continue

        if os.path.exists(output_path):
            output_files.append(output_path)
            if progress_callback:
                progress_callback(i + 1, len(all_points) - 1, output_path)

    return output_files


def build_restoration_filter(settings: dict) -> str:
    """Build FFmpeg audio filter string from restoration settings dict.

    settings shape (matches CleanupAudioTab.get_settings()):
        {"highpass": {"enabled": bool, "cutoff": int},
         "declick": {"enabled": bool, "strength": float},
         "denoise": {"enabled": bool, "strength": float}}

    Returns empty string if no filters are needed.
    """
    filters: list[str] = []

    if settings.get("highpass", {}).get("enabled"):
        cutoff = settings["highpass"]["cutoff"]
        filters.append(f"highpass=f={cutoff}")

    if settings.get("declick", {}).get("enabled"):
        filters.append("adeclick")

    if settings.get("denoise", {}).get("enabled"):
        strength = settings["denoise"]["strength"]  # 0.0 to 1.0
        # Map 0-1 to anlmdn strength 1-15 (sensible range for vinyl noise)
        anlmdn_s = max(1, min(15, int(strength * 15)))
        filters.append(f"anlmdn=s={anlmdn_s}")

    return ",".join(filters) if filters else ""


def apply_restoration(
    input_file: str,
    output_file: str,
    settings: dict,
    samplerate: int | None = None,
) -> bool:
    """Apply restoration filters to audio file using FFmpeg.

    Args:
        input_file: Path to input WAV file.
        output_file: Path to output file.
        settings: Restoration settings dict (same shape as
                  CleanupAudioTab.get_settings()).
        samplerate: Output sample rate (None = keep original).

    Returns:
        True if FFmpeg completed successfully.
    """
    ffmpeg = _find_ffmpeg()
    filter_str = build_restoration_filter(settings)

    cmd: list[str] = [ffmpeg, "-y", "-v", "error", "-i", input_file]

    if filter_str:
        cmd.extend(["-af", filter_str])

    if samplerate:
        cmd.extend(["-ar", str(samplerate)])

    # Copy to WAV unless output already specifies a format
    if not output_file.lower().endswith((".wav", ".flac", ".mp3", ".aiff", ".aif", ".ogg", ".au", ".raw")):
        cmd.extend(["-c:a", "pcm_s16le"])

    cmd.append(output_file)

    result = subprocess.run(cmd, capture_output=True, timeout=300)
    return result.returncode == 0


def convert_audio(
    input_file: str,
    output_file: str,
    output_format: str = "flac",
    flac_compression: int = 8,
    mp3_quality: str = "0",
    restoration_level: int = 0,
    restoration_settings: dict | None = None,
) -> bool:
    """Convert audio file to specified format with optional restoration.

    Args:
        restoration_settings: Dict from CleanupAudioTab.get_settings().
                             Takes precedence over restoration_level when provided.
    """
    ffmpeg = _find_ffmpeg()

    if restoration_settings:
        af_filter_str = build_restoration_filter(restoration_settings)
    else:
        af_filters: list[str] = []
        if restoration_level >= 1:
            af_filters.append("highpass=f=30")
        if restoration_level >= 2:
            af_filters.append("adeclick")
        af_filter_str = ",".join(af_filters) if af_filters else "anull"

    cmd = [ffmpeg, "-y", "-v", "error", "-i", input_file]

    if af_filter_str and af_filter_str != "anull":
        cmd.extend(["-af", af_filter_str])

    if output_format == "flac":
        cmd.extend(["-c:a", "flac", "-compression_level", str(flac_compression)])
    elif output_format == "mp3":
        cmd.extend(["-c:a", "libmp3lame", "-q:a", mp3_quality])
    elif output_format == "aiff":
        cmd.extend(["-c:a", "pcm_s16be"])
    else:
        cmd.extend(["-c:a", "flac", "-compression_level", str(flac_compression)])

    cmd.append(output_file)

    result = subprocess.run(cmd, capture_output=True, timeout=300)
    return result.returncode == 0


def embed_cover_art(
    audio_file: str, cover_data: bytes, mime_type: str = "image/jpeg"
) -> bool:
    """Embed cover art into audio file using FFmpeg."""
    ffmpeg = _find_ffmpeg()

    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=f".{mime_type.split('/')[-1]}", delete=False
    ) as f:
        f.write(cover_data)
        cover_file = f.name

    try:
        output_file = audio_file + ".tmp"
        cmd = [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            audio_file,
            "-i",
            cover_file,
            "-map",
            "0:a",
            "-map",
            "1:v",
            "-c:a",
            "copy",
            "-c:v",
            "mjpeg",
            "-disposition:v",
            "attached_pic",
            "-metadata:s:v",
            "title=Album cover",
            "-metadata:s:v",
            "comment=Cover (front)",
            output_file,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            os.replace(output_file, audio_file)
            return True
        return False
    finally:
        try:
            os.unlink(cover_file)
        except OSError:
            pass
