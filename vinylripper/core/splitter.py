import re
import numpy as np
import soundfile as sf
from vinylripper.core.recorder import write_tags


def _to_mono(audio):
    if audio.ndim > 1:
        return audio.mean(axis=1)
    return audio.copy()


def detect_silence_splits(audio, samplerate, threshold_db=-40, min_silence_ms=300):
    if len(audio) < samplerate:
        return []

    mono = _to_mono(audio)
    window_size = int(samplerate * 0.05)
    threshold = 10 ** (threshold_db / 20)

    n_frames = len(mono) // window_size
    if n_frames < 3:
        return []

    mono = mono[: n_frames * window_size]
    windows = mono.reshape(n_frames, window_size)
    rms = np.sqrt(np.mean(windows**2, axis=1))
    silent = rms < threshold

    silences = []
    i = 0
    while i < n_frames:
        if silent[i]:
            start = i
            while i < n_frames and silent[i]:
                i += 1
            silences.append((start, i - start))
        else:
            i += 1

    min_w = int(min_silence_ms / 50)
    silences = [(s, d) for s, d in silences if d >= min_w]
    if not silences:
        return []

    first_nonsilent = 0
    for j in range(n_frames):
        if not silent[j]:
            first_nonsilent = j
            break

    last_nonsilent = n_frames - 1
    for j in range(n_frames - 1, -1, -1):
        if not silent[j]:
            last_nonsilent = j
            break

    silences = [
        (s, d) for s, d in silences if s > first_nonsilent and s + d < last_nonsilent
    ]

    split_points = [(s + d // 2) * window_size for s, d in silences]

    return split_points


def split_audio(audio, split_points):
    segments = []
    prev = 0
    for sp in split_points:
        if sp > prev:
            segments.append(audio[prev:sp])
        prev = sp
    if prev < len(audio):
        segments.append(audio[prev:])
    return [s for s in segments if len(s) > 0]


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "untitled"


def save_track(
    filepath,
    data,
    samplerate,
    album_metadata=None,
    track_position=None,
    track_title=None,
):
    sf.write(filepath, data, samplerate)
    if album_metadata is not None:
        write_tags(
            filepath,
            album_metadata,
            track_position=track_position,
            track_title=track_title,
        )
