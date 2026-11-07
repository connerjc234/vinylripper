import queue
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf

# How much recent audio to keep for get_recent_audio(). The full recording is
# accumulated by the caller (RecordingSession); keeping all of it here too would
# double memory use on long, high-sample-rate sides.
_HISTORY_SECS = 30


class Recorder:
    def __init__(
        self,
        device=None,
        samplerate=44100,
        channels=2,
        blocksize=4096,
        history_secs=_HISTORY_SECS,
    ):
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self._blocksize = blocksize
        # Unbounded: the UI drains this every few tens of milliseconds. A bounded
        # queue would silently drop audio (gaps in the rip) whenever the UI
        # thread stalls for longer than the queue's capacity.
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = None
        self._recording = False
        self._paused = False
        self._history_frames = max(0, int(history_secs * samplerate))
        self._recent: deque[np.ndarray] = deque()
        self._recent_len = 0
        self._overflows = 0

    @property
    def is_recording(self):
        return self._recording

    @property
    def is_paused(self):
        return self._paused

    @property
    def overflow_count(self):
        """Input overflows reported by the audio driver since start().

        Each overflow means the driver discarded input, so the recording has a
        small gap at that point.
        """
        return self._overflows

    def start(self):
        if self._recording:
            return
        self._recent.clear()
        self._recent_len = 0
        self._overflows = 0
        self._recording = True
        self._stream = sd.InputStream(
            device=self.device,
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=self._blocksize,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        """Stop and close the input stream.

        Audio still waiting in the queue stays there; call drain() first to
        collect it.
        """
        if not self._recording:
            return
        self._recording = False
        self._paused = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def pause(self):
        if not self._recording or self._paused:
            return
        self._paused = True
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def resume(self):
        if not self._recording or not self._paused:
            return
        self._paused = False
        self._stream = sd.InputStream(
            device=self.device,
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=self._blocksize,
            callback=self._callback,
        )
        self._stream.start()

    def get_recent_audio(self, duration_secs):
        """Return up to the last ``duration_secs`` of drained audio.

        Limited to the recorder's history window (30 s by default).
        """
        if not self._recent:
            return np.array([])
        n = int(duration_secs * self.samplerate)
        # Only concatenate the blocks needed to cover n frames.
        blocks = []
        total = 0
        for block in reversed(self._recent):
            blocks.append(block)
            total += len(block)
            if total >= n:
                break
        recent = np.concatenate(blocks[::-1], axis=0)
        return recent[-n:] if len(recent) > n else recent

    def save(self, filepath, data, metadata=None):
        sf.write(filepath, data, self.samplerate)
        if metadata is not None:
            write_tags(filepath, metadata)

    def drain(self):
        frames = []
        while True:
            try:
                frames.append(self._queue.get_nowait())
            except queue.Empty:
                break
        for block in frames:
            self._recent.append(block)
            self._recent_len += len(block)
        # Trim history, keeping at least _history_frames.
        while (
            self._recent
            and self._recent_len - len(self._recent[0]) >= self._history_frames
        ):
            self._recent_len -= len(self._recent.popleft())
        return frames

    def _callback(self, indata, frames, time_info, status):
        if status and status.input_overflow:
            self._overflows += 1
        self._queue.put_nowait(indata.copy())

    def list_input_devices(self):
        devices = sd.query_devices()
        return [d for d in devices if d["max_input_channels"] > 0]


def write_tags(filepath, metadata, track_position=None, track_title=None):
    try:
        from mutagen.flac import FLAC, Picture
    except ImportError:
        return

    if not filepath.lower().endswith(".flac"):
        return

    try:
        audio = FLAC(filepath)
    except Exception:
        return

    if metadata.artist:
        audio["ARTIST"] = metadata.artist
    if metadata.title:
        audio["ALBUM"] = metadata.title
    if metadata.year:
        audio["DATE"] = str(metadata.year)
    if metadata.label:
        audio["ORGANIZATION"] = metadata.label
    if metadata.catalog_number:
        audio["CATALOGNUMBER"] = metadata.catalog_number
    if metadata.genres:
        audio["GENRE"] = ", ".join(metadata.genres)
    if metadata.styles:
        audio["STYLE"] = ", ".join(metadata.styles)
    if metadata.tracklist:
        lines = []
        for t in metadata.tracklist:
            pos = t.get("position", "")
            title = t.get("title", "")
            dur = t.get("duration", "")
            parts = [p for p in [pos, title, dur] if p]
            lines.append("  ".join(parts))
        audio["TRACKLIST"] = "\n".join(lines)
    if track_title:
        audio["TITLE"] = track_title
    if track_position is not None:
        audio["TRACKNUMBER"] = str(track_position)
    if metadata.cover_data:
        pic = Picture()
        pic.data = metadata.cover_data
        pic.type = 3
        pic.mime = metadata.cover_mime
        pic.width = 0
        pic.height = 0
        pic.depth = 0
        pic.colors = 0
        pic.desc = ""
        audio.add_picture(pic)
    try:
        audio.save()
    except Exception:
        pass
