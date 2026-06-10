import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QFileDialog, QStatusBar,
    QMessageBox, QSlider,
)
from PyQt6.QtCore import Qt, QTimer

from vinylripper.core.recorder import Recorder
from vinylripper.core.splitter import detect_silence_splits, split_audio, save_track, _safe_filename
from vinylripper.ui.waveform_widget import WaveformWidget
from vinylripper.ui.search_dialog import SearchDialog
from vinylripper.core.metadata import AlbumMetadata

STYLE = """
QMainWindow {
    background-color: #1a1a20;
}
QWidget {
    background-color: #1a1a20;
    color: #d0d0d8;
    font-family: "Cantarell", "Noto Sans", sans-serif;
    font-size: 12px;
}
QPushButton {
    background-color: #2a2a35;
    border: 1px solid #3a3a48;
    border-radius: 5px;
    padding: 6px 18px;
    color: #d0d0d8;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #353548;
    border-color: #4a4a5a;
}
QPushButton:pressed {
    background-color: #3a3a50;
}
QPushButton:disabled {
    background-color: #22222a;
    color: #555;
    border-color: #2a2a32;
}
QComboBox {
    background-color: #2a2a35;
    border: 1px solid #3a3a48;
    border-radius: 5px;
    padding: 4px 8px;
    color: #d0d0d8;
    min-width: 200px;
}
QComboBox:hover {
    border-color: #4a4a5a;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #2a2a35;
    color: #d0d0d8;
    selection-background-color: #3a3a50;
    border: 1px solid #3a3a48;
}
QLabel {
    background: transparent;
    color: #a0a0b0;
    font-weight: bold;
    font-size: 11px;
}
QStatusBar {
    background-color: #141418;
    color: #888;
    font-size: 11px;
    border-top: 1px solid #2a2a32;
}
QStatusBar::item {
    border: none;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VinylRipper")
        self.setMinimumSize(860, 540)
        self.setStyleSheet(STYLE)

        self._recorder = Recorder()
        self._recording = False
        self._recorded_data = None
        self._album_metadata = None

        self._build_ui()
        self._populate_devices()
        self._setup_timer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._waveform = WaveformWidget()
        self._waveform.markers_changed.connect(self._on_markers_changed)
        layout.addWidget(self._waveform, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self._record_btn = QPushButton("Record")
        self._record_btn.setFixedHeight(32)
        self._record_btn.clicked.connect(self._toggle_recording)
        controls.addWidget(self._record_btn)

        self._save_btn = QPushButton("Save As...")
        self._save_btn.setFixedHeight(32)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_recording)
        controls.addWidget(self._save_btn)

        self._split_btn = QPushButton("Split Tracks")
        self._split_btn.setFixedHeight(32)
        self._split_btn.setEnabled(False)
        self._split_btn.clicked.connect(self._split_recording)
        controls.addWidget(self._split_btn)

        self._metadata_label = QLabel()
        controls.addWidget(self._metadata_label, 1)

        controls.addSpacing(12)

        label = QLabel("Input Device")
        controls.addWidget(label)

        self._device_combo = QComboBox()
        self._device_combo.setFixedHeight(30)
        controls.addWidget(self._device_combo, 1)

        layout.addLayout(controls)

        split_row = QHBoxLayout()
        split_row.setSpacing(8)

        self._threshold_label = QLabel("Silence:")
        split_row.addWidget(self._threshold_label)
        self._less_label = QLabel("Fine")
        self._less_label.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(self._less_label)
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(20, 60)
        self._threshold_slider.setValue(40)
        self._threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._threshold_slider.setTickInterval(5)
        self._threshold_slider.valueChanged.connect(self._on_threshold_changed)
        split_row.addWidget(self._threshold_slider, 1)
        self._more_label = QLabel("Strict")
        self._more_label.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(self._more_label)

        split_row.addSpacing(16)

        self._duration_label = QLabel("Min Gap:")
        split_row.addWidget(self._duration_label)
        self._short_label = QLabel("Short")
        self._short_label.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(self._short_label)
        self._duration_slider = QSlider(Qt.Orientation.Horizontal)
        self._duration_slider.setRange(100, 2000)
        self._duration_slider.setValue(300)
        self._duration_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._duration_slider.setTickInterval(100)
        self._duration_slider.valueChanged.connect(self._on_duration_changed)
        split_row.addWidget(self._duration_slider, 1)
        self._long_label = QLabel("Long")
        self._long_label.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(self._long_label)

        self._split_status = QLabel("Ready — record to preview splits")
        self._split_status.setStyleSheet("color: #666;")
        split_row.addWidget(self._split_status, 1)

        layout.addLayout(split_row)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    def _populate_devices(self):
        devices = self._recorder.list_input_devices()
        default = None
        for i, d in enumerate(devices):
            name = d["name"]
            ch = d["max_input_channels"]
            self._device_combo.addItem(f"{name}  ({ch} ch)", i)
            if d.get("default"):
                default = i
        if default is not None:
            self._device_combo.setCurrentIndex(default)

    def _setup_timer(self):
        self._timer = QTimer()
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._poll_audio)
        self._timer.start()

    def _poll_audio(self):
        if not self._recording:
            return
        for data in self._recorder.drain():
            self._waveform.enqueue(data)

    def _toggle_recording(self):
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        idx = self._device_combo.currentData()
        ds = self._recorder.list_input_devices()
        if idx is None or idx >= len(ds):
            self._status.showMessage("No valid input device selected")
            return

        dialog = SearchDialog(self)
        if dialog.exec() != SearchDialog.DialogCode.Accepted:
            return

        self._album_metadata = dialog.album_metadata
        if self._album_metadata and self._album_metadata.artist:
            self._metadata_label.setText(
                f"{self._album_metadata.artist} — {self._album_metadata.title}"
            )
        else:
            self._metadata_label.setText("")

        device_info = ds[idx]
        self._recorder = Recorder(
            device=idx,
            samplerate=int(device_info["default_samplerate"]),
            channels=min(2, device_info["max_input_channels"]),
        )
        self._recorder.start()
        self._recording = True
        self._waveform.set_samplerate(int(device_info["default_samplerate"]))
        self._waveform.set_recording(True)
        self._record_btn.setText("Stop")
        self._save_btn.setEnabled(False)
        self._split_btn.setEnabled(False)
        self._device_combo.setEnabled(False)
        self._waveform.clear_review()
        self._waveform.reset()
        self._status.showMessage("Recording...")

    def _stop_recording(self):
        data = self._recorder.stop()
        self._recording = False
        self._waveform.set_recording(False)
        self._record_btn.setText("Record")
        self._device_combo.setEnabled(True)
        if data is not None and len(data) > 0:
            self._recorded_data = data
            self._save_btn.setEnabled(True)
            sr = self._recorder.samplerate
            self._waveform.set_full_audio(data, sr)
            has_tracks = bool(self._album_metadata and self._album_metadata.tracklist)
            self._split_btn.setEnabled(has_tracks)
            if has_tracks:
                self._update_split_preview()
            else:
                self._split_status.setText("Split & save available after Discogs search")
            dur = len(data) / sr
            self._status.showMessage(f"Recorded {dur:.1f}s — ready to save")
        else:
            self._recorded_data = None
            self._save_btn.setEnabled(False)
            self._split_btn.setEnabled(False)
            self._status.showMessage("No audio recorded")

    def _on_threshold_changed(self, value):
        self._update_split_preview()

    def _on_duration_changed(self, value):
        self._update_split_preview()

    def _on_markers_changed(self, markers):
        n = len(markers) + 1
        track_count = len(self._album_metadata.tracklist) if self._album_metadata else 0
        label = f"{n} tracks"
        if track_count and n != track_count:
            label += f"  ({track_count} in metadata)"
        self._split_status.setText(label)

    def _update_split_preview(self):
        if self._recorded_data is None:
            return
        threshold_db = -(self._threshold_slider.value())
        min_silence_ms = self._duration_slider.value()
        try:
            sr = self._recorder.samplerate
            points = detect_silence_splits(self._recorded_data, sr,
                                           threshold_db=threshold_db,
                                           min_silence_ms=min_silence_ms)
            self._waveform.set_split_markers(points)
            n = len(points) + 1
            label = f"Detected {n} tracks" if points else "No gaps detected"
            track_count = len(self._album_metadata.tracklist) if self._album_metadata else 0
            if track_count and n != track_count:
                label += f"  ({track_count} in metadata)"
            self._split_status.setText(label)
        except Exception:
            self._split_status.setText("")

    def _split_recording(self):
        if self._recorded_data is None:
            return

        sr = self._recorder.samplerate
        split_points = self._waveform.get_split_markers()
        if not split_points:
            QMessageBox.information(self, "No Splits",
                                    "Place split markers on the waveform first "
                                    "by adjusting the sensitivity slider or dragging markers.")
            return

        segments = split_audio(self._recorded_data, split_points)
        if len(segments) < 2:
            QMessageBox.information(self, "No Splits Found",
                                    "Could not split with current marker positions.")
            return

        n_detected = len(segments)
        n_tracks = len(self._album_metadata.tracklist) if self._album_metadata else 0

        if n_tracks and n_detected != n_tracks:
            ans = QMessageBox.question(
                self, "Track Count Mismatch",
                f"Detected {n_detected} tracks, but Discogs metadata has "
                f"{n_tracks} tracks.\n\nSplit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        dir_path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if not dir_path:
            return

        self._split_btn.setEnabled(False)

        saved = 0
        for i, seg in enumerate(segments):
            if len(seg) < sr * 2:
                continue
            track_num = i + 1
            track_title = ""
            if self._album_metadata and track_num <= n_tracks:
                t = self._album_metadata.tracklist[track_num - 1]
                track_title = t.get("title", "")

            if track_title:
                label = f"{track_num:02d}. {_safe_filename(track_title)}.flac"
            else:
                label = f"Track {track_num:02d}.flac"

            filepath = os.path.join(dir_path, label)
            try:
                save_track(filepath, seg, sr, self._album_metadata,
                           track_position=track_num, track_title=track_title)
                saved += 1
            except Exception as e:
                self._status.showMessage(f"Error saving {label}: {e}")

        self._split_btn.setEnabled(True)
        self._status.showMessage(f"Split complete — saved {saved} tracks to {dir_path}")

    def _save_recording(self):
        if self._recorded_data is None:
            return
        filters = (
            "FLAC (*.flac);;"
            "WAV (*.wav);;"
            "OGG Vorbis (*.ogg);;"
            "AIFF (*.aiff *.aif);;"
            "AU (*.au);;"
            "RAW (*.raw)"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audio", "recording.flac", filters
        )
        if not path:
            return
        try:
            self._recorder.save(path, self._recorded_data, self._album_metadata)
            self._status.showMessage(f"Saved  {path}")
        except Exception as e:
            self._status.showMessage(f"Save failed: {e}")
