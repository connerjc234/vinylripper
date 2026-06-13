import queue

import numpy as np
import sounddevice as sd
import soundfile as sf

_QUEUE_MAXSIZE = 16


class Recorder:
    def __init__(self, device=None, samplerate=44100, channels=2, blocksize=4096):
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self._blocksize = blocksize
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._stream = None
        self._recording = False
        self._paused = False
        self._frames = []

    @property
    def is_recording(self):
        return self._recording

    @property
    def is_paused(self):
        return self._paused

    def start(self):
        if self._recording:
            return
        self._frames = []
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
        if not self._recording:
            return
        self._recording = False
        self._paused = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        return np.concatenate(self._frames, axis=0) if self._frames else np.array([])

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
        if not self._frames:
            return np.array([])
        all_frames = np.concatenate(self._frames, axis=0)
        n = int(duration_secs * self.samplerate)
        if len(all_frames) <= n:
            return all_frames
        return all_frames[-n:]

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
        self._frames.extend(frames)
        return frames

    def _callback(self, indata, frames, time_info, status):
        try:
            self._queue.put_nowait(indata.copy())
        except queue.Full:
            pass

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
        pic.desc = b""
        audio.add_picture(pic)
    try:
        audio.save()
    except Exception:
        pass
