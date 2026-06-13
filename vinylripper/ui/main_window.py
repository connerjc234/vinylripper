import os
import threading

import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from vinylripper.core.audio_processor import (
    convert_audio,
    embed_cover_art,
    split_audio_ffmpeg,
)
from vinylripper.core.config import get_config
from vinylripper.core.recorder import Recorder
from vinylripper.core.splitter import detect_silence_splits
from vinylripper.ui.search_dialog import SearchDialog
from vinylripper.ui.settings_dialog import SettingsDialog
from vinylripper.ui.waveform_widget import WaveformWidget

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
    _processing_finished = pyqtSignal(int, str, str)
    _save_finished = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VinylRipper")
        self.setMinimumSize(860, 540)
        self.setStyleSheet(STYLE)

        self._config = get_config()
        self.resize(self._config.window_width, self._config.window_height)

        self._recorder = Recorder()
        self._recording = False
        self._recorded_data = None
        self._album_metadata = None
        self._side = 1
        self._temp_wav_path = None

        self._side_check_timer = QTimer()
        self._side_check_timer.setInterval(3000)
        self._side_check_timer.timeout.connect(self._check_side_end)

        self._resume_timer = QTimer()
        self._resume_timer.setInterval(1000)
        self._resume_timer.timeout.connect(self._try_resume_recording)

        self._processing_thread = None
        self._cancel_event = threading.Event()
        self._processing_finished.connect(self._on_processing_finished)
        self._save_finished.connect(self._on_save_finished)

        self._build_ui()
        self._populate_devices()
        self._setup_timer()
        self._setup_shortcuts()
        self._load_window_state()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #1a1a20;
                border: none;
                spacing: 4px;
                padding: 4px;
            }
            QToolButton {
                background-color: #2a2a35;
                border: 1px solid #3a3a48;
                border-radius: 4px;
                padding: 4px 10px;
                color: #d0d0d8;
            }
            QToolButton:hover {
                background-color: #353548;
                border-color: #4a4a5a;
            }
            QToolButton:disabled {
                background-color: #22222a;
                color: #555;
                border-color: #2a2a32;
            }
        """)
        self.addToolBar(toolbar)

        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._undo)
        self._undo_action.setEnabled(False)
        toolbar.addAction(self._undo_action)

        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._redo)
        self._redo_action.setEnabled(False)
        toolbar.addAction(self._redo_action)

        toolbar.addSeparator()

        self._settings_action = QAction("Settings", self)
        self._settings_action.triggered.connect(self._show_settings)
        toolbar.addAction(self._settings_action)

        toolbar.addSeparator()

        self._output_format_combo = QComboBox()
        self._output_format_combo.addItems(["FLAC", "MP3", "AIFF"])
        self._output_format_combo.setCurrentText(self._config.default_output_format.upper())
        self._output_format_combo.setFixedWidth(100)
        toolbar.addWidget(self._output_format_combo)

        self._output_quality_combo = QComboBox()
        self._output_quality_combo.setFixedWidth(160)
        self._update_quality_options()
        self._output_format_combo.currentTextChanged.connect(self._update_quality_options)
        toolbar.addWidget(self._output_quality_combo)

        toolbar.addSeparator()

        self._restoration_combo = QComboBox()
        self._restoration_combo.addItems(["None", "Highpass (rumble)", "Highpass + Declick"])
        self._restoration_combo.setCurrentIndex(self._config.default_restoration_level)
        self._restoration_combo.setFixedWidth(160)
        toolbar.addWidget(self._restoration_combo)

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

        self._split_btn = QPushButton("Split & Export")
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
        self._threshold_slider.setValue(int(-self._config.silence_threshold_db))
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
        self._duration_slider.setRange(100, 5000)
        self._duration_slider.setValue(int(self._config.min_silence_duration * 1000))
        self._duration_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._duration_slider.setTickInterval(500)
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

    def _setup_shortcuts(self):
        # Undo/Redo shortcuts
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self._undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self._redo)

        # Delete key to remove selected marker
        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        delete_shortcut.activated.connect(self._delete_selected_marker)

    def _load_window_state(self):
        # Window size already set in __init__ from config
        pass

    def _save_window_state(self):
        self._config.set("window_width", self.width())
        self._config.set("window_height", self.height())
        self._config.save()

    def _update_quality_options(self):
        fmt = self._output_format_combo.currentText().lower()
        self._output_quality_combo.clear()
        if fmt == "flac":
            self._output_quality_combo.addItems([f"Compression {i} (0=fast, 8=best)" for i in range(9)])
            self._output_quality_combo.setCurrentIndex(self._config.default_flac_compression)
        elif fmt == "mp3":
            self._output_quality_combo.addItems([
                "VBR 0 (~245 kbps, best)",
                "VBR 1 (~225 kbps)",
                "VBR 2 (~190 kbps, default)",
                "VBR 3 (~175 kbps)",
                "VBR 4 (~165 kbps)",
                "VBR 5 (~130 kbps)",
                "VBR 6 (~115 kbps)",
                "VBR 7 (~100 kbps)",
                "VBR 8 (~85 kbps)",
                "VBR 9 (~65 kbps)",
            ])
            self._output_quality_combo.setCurrentText(f"VBR {self._config.default_mp3_quality} (~245 kbps, best)" if self._config.default_mp3_quality == "0" else f"VBR {self._config.default_mp3_quality}")
        elif fmt == "aiff":
            self._output_quality_combo.addItems(["16-bit PCM", "24-bit PCM", "32-bit Float"])
            self._output_quality_combo.setCurrentIndex(0)

    def _undo(self):
        if self._waveform.undo():
            self._update_undo_redo_actions()
            self._status.showMessage("Undo", 2000)

    def _redo(self):
        if self._waveform.redo():
            self._update_undo_redo_actions()
            self._status.showMessage("Redo", 2000)

    def _update_undo_redo_actions(self):
        self._undo_action.setEnabled(self._waveform.can_undo())
        self._redo_action.setEnabled(self._waveform.can_redo())

    def _delete_selected_marker(self):
        # Could implement marker deletion with right-click context menu
        pass

    def _show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Reload config values
            self._threshold_slider.setValue(int(-self._config.silence_threshold_db))
            self._duration_slider.setValue(int(self._config.min_silence_duration * 1000))
            self._restoration_combo.setCurrentIndex(self._config.default_restoration_level)
            self._output_format_combo.setCurrentText(self._config.default_output_format.upper())
            self._update_quality_options()
            self._status.showMessage("Settings saved", 2000)

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

        # Create temp WAV file for recording
        import tempfile
        self._temp_wav_path = tempfile.mktemp(suffix=".wav")

        self._recorder.start()
        self._recording = True
        self._side = 1
        self._side_check_timer.start()
        self._waveform.set_samplerate(int(device_info["default_samplerate"]))
        self._waveform.set_recording(True)
        self._record_btn.setText("Stop")
        self._save_btn.setEnabled(False)
        self._split_btn.setEnabled(False)
        self._device_combo.setEnabled(False)
        self._waveform.clear_review()
        self._waveform.reset()
        self._waveform.clear_undo_stack()
        self._update_undo_redo_actions()
        self._status.showMessage("Recording...")

    def _stop_recording(self):
        self._side_check_timer.stop()
        self._resume_timer.stop()
        data = self._recorder.stop()
        self._recording = False
        self._side = 1
        self._waveform.set_recording(False)
        self._record_btn.setText("Record")
        self._device_combo.setEnabled(True)

        if data is not None and len(data) > 0:
            self._recorded_data = data
            self._save_btn.setEnabled(True)
            sr = self._recorder.samplerate

            # Save to temp WAV file for FFmpeg processing
            import soundfile as sf
            if self._temp_wav_path:
                sf.write(self._temp_wav_path, data, sr)

            self._waveform.set_full_audio(data, sr)
            has_tracks = bool(self._album_metadata and self._album_metadata.tracklist)
            self._split_btn.setEnabled(has_tracks)
            if has_tracks:
                self._update_split_preview()
            else:
                self._split_status.setText(
                    "Split & save available after Discogs search"
                )
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

    def _check_side_end(self):
        if self._recorder.is_paused:
            return
        recent = self._recorder.get_recent_audio(15)
        sr = self._recorder.samplerate
        if len(recent) < sr * 3:
            return

        if recent.ndim > 1:
            mono = recent.mean(axis=1)
        else:
            mono = recent.copy()

        threshold = 10 ** (-45 / 20)
        window = sr
        n_windows = min(10, len(mono) // window)
        if n_windows < 3:
            return

        silent = 0
        for i in range(n_windows):
            chunk = mono[-(i + 1) * window:len(mono) - i * window] if i else mono[-window:]
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms < threshold:
                silent += 1
            else:
                silent = 0

        if silent >= 8:
            self._on_side_finished()

    def _on_side_finished(self):
        self._recorder.pause()
        self._side_check_timer.stop()
        self._waveform.set_recording(False)

        QMessageBox.information(
            self,
            f"Side {self._side} Complete",
            f"Side {self._side} finished. Flip the record and drop the needle.\n"
            "Recording will resume automatically when audio is detected.",
        )

        self._status.showMessage(f"Waiting for Side {self._side + 1}...")
        self._resume_timer.start()

    def _try_resume_recording(self):
        if not self._recorder.is_paused:
            self._resume_timer.stop()
            return
        try:
            import sounddevice as sd
            temp = sd.rec(
                int(self._recorder.samplerate),
                samplerate=self._recorder.samplerate,
                channels=1,
                device=self._recorder.device,
                blocking=True,
            )
            rms = np.sqrt(np.mean(temp ** 2))
            if rms > 10 ** (-35 / 20):
                self._on_audio_detected()
        except Exception:
            pass

    def _on_audio_detected(self):
        self._resume_timer.stop()
        self._side += 1
        self._recorder.resume()
        self._waveform.set_recording(True)
        self._side_check_timer.start()
        self._status.showMessage(f"Recording Side {self._side}...")

    def _update_split_preview(self):
        if self._recorded_data is None:
            return
        threshold_db = -(self._threshold_slider.value())
        min_silence_ms = self._duration_slider.value()
        try:
            sr = self._recorder.samplerate
            points = detect_silence_splits(
                self._recorded_data,
                sr,
                threshold_db=threshold_db,
                min_silence_ms=min_silence_ms,
            )
            self._waveform.set_split_markers(points)
            n = len(points) + 1
            label = f"Detected {n} tracks" if points else "No gaps detected"
            track_count = (
                len(self._album_metadata.tracklist) if self._album_metadata else 0
            )
            if track_count and n != track_count:
                label += f"  ({track_count} in metadata)"
            self._split_status.setText(label)
        except Exception:
            self._split_status.setText("")

    def _split_recording(self):
        if self._recorded_data is None or not self._temp_wav_path:
            return

        split_points = self._waveform.get_split_markers()
        if not split_points:
            QMessageBox.information(
                self,
                "No Splits",
                "Place split markers on the waveform first "
                "by adjusting the sensitivity slider or dragging markers.",
            )
            return

        sr = self._recorder.samplerate
        split_points_sec = [p / sr for p in split_points]

        n_detected = len(split_points_sec) + 1
        n_tracks = len(self._album_metadata.tracklist) if self._album_metadata else 0

        if n_tracks and n_detected != n_tracks:
            ans = QMessageBox.question(
                self,
                "Track Count Mismatch",
                f"Detected {n_detected} tracks, but Discogs metadata has "
                f"{n_tracks} tracks.\n\nSplit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        dir_path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if not dir_path:
            return

        self._config.last_output_dir = dir_path
        self._config.save()

        self._split_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._record_btn.setEnabled(False)
        self._device_combo.setEnabled(False)
        self._output_format_combo.setEnabled(False)
        self._output_quality_combo.setEnabled(False)
        self._restoration_combo.setEnabled(False)
        self._status.showMessage("Processing tracks...")

        self._cancel_event.clear()

        # Prepare track metadata
        track_metadata = []
        if self._album_metadata:
            for i in range(n_detected):
                track_metadata.append(self._album_metadata.get_track_metadata(i))
        else:
            for i in range(n_detected):
                track_metadata.append({
                    "position": str(i + 1),
                    "title": f"Track {i + 1}",
                    "artist": "",
                    "album": "",
                })

        # Get output format and quality
        fmt = self._output_format_combo.currentText().lower()
        quality_text = self._output_quality_combo.currentText()

        if fmt == "flac":
            flac_compression = int(quality_text.split()[1].split("(")[0]) if "Compression" in quality_text else self._config.default_flac_compression
            mp3_quality = "0"
        elif fmt == "mp3":
            flac_compression = 8
            if "VBR" in quality_text:
                mp3_quality = quality_text.split("VBR")[1].split("(")[0].strip()
            else:
                mp3_quality = self._config.default_mp3_quality
        else:
            flac_compression = 8
            mp3_quality = "0"

        restoration_level = self._restoration_combo.currentIndex()

        # Run processing in background thread
        self._processing_thread = threading.Thread(
            target=self._process_tracks_thread,
            args=(self._temp_wav_path, dir_path, split_points_sec, track_metadata,
                  fmt, flac_compression, mp3_quality, restoration_level),
            daemon=True
        )
        self._processing_thread.start()

    _save_finished = pyqtSignal(bool, str, str)

    def _save_recording(self):
        if self._recorded_data is None or not self._temp_wav_path:
            return

        fmt = self._output_format_combo.currentText().lower()
        filters = {
            "flac": "FLAC (*.flac)",
            "mp3": "MP3 (*.mp3)",
            "aiff": "AIFF (*.aiff *.aif)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audio", f"recording.{fmt}", filters.get(fmt, "FLAC (*.flac)")
        )
        if not path:
            return

        fmt = self._output_format_combo.currentText().lower()
        quality_text = self._output_quality_combo.currentText()

        if fmt == "flac":
            flac_compression = int(quality_text.split()[1].split("(")[0]) if "Compression" in quality_text else self._config.default_flac_compression
        elif fmt == "mp3":
            if "VBR" in quality_text:
                mp3_quality = quality_text.split("VBR")[1].split("(")[0].strip()
            else:
                mp3_quality = self._config.default_mp3_quality
        else:
            flac_compression = 8
            mp3_quality = "0"

        restoration_level = self._restoration_combo.currentIndex()

        self._save_btn.setEnabled(False)
        self._status.showMessage("Converting...")

        def convert_thread():
            try:
                temp_path = self._temp_wav_path
                if not temp_path:
                    self._save_finished.emit(False, "", "No temporary file available")
                    return
                success = convert_audio(
                    temp_path,
                    path,
                    output_format=fmt,
                    flac_compression=flac_compression,
                    mp3_quality=mp3_quality,
                    restoration_level=restoration_level,
                )
                if success and self._album_metadata and self._album_metadata.cover_data:
                    embed_cover_art(path, self._album_metadata.cover_data, self._album_metadata.cover_mime)
                self._save_finished.emit(success, path, None if success else "Conversion failed")
            except Exception as e:
                self._save_finished.emit(False, "", str(e))

        threading.Thread(target=convert_thread, daemon=True).start()

    def _on_save_finished(self, success, path, error):
        self._save_btn.setEnabled(True)
        if success:
            self._status.showMessage(f"Saved: {path}")
        else:
            self._status.showMessage(f"Save failed: {error}")
            QMessageBox.critical(self, "Save Error", error or "Unknown error")

    def _process_tracks_thread(self, input_file, output_dir, split_points, track_metadata,
                                fmt, flac_compression, mp3_quality, restoration_level):
        try:
            output_files = split_audio_ffmpeg(
                input_file,
                output_dir,
                split_points,
                track_metadata,
                output_format=fmt,
                flac_compression=flac_compression,
                mp3_quality=mp3_quality,
                restoration_level=restoration_level,
                progress_callback=self._on_track_progress,
                cancel_event=self._cancel_event,
            )

            # Embed cover art if available
            if self._album_metadata and self._album_metadata.cover_data:
                for f in output_files:
                    embed_cover_art(f, self._album_metadata.cover_data, self._album_metadata.cover_mime)

            self._processing_finished.emit(len(output_files), output_dir, None)
        except Exception as e:
            self._processing_finished.emit(0, "", str(e))

    _processing_finished = pyqtSignal(int, str, str)

    def _on_track_progress(self, current, total, filepath):
        self._status.showMessage(f"Processing track {current}/{total}...")

    def _on_processing_finished(self, count, output_dir, error):
        self._split_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._record_btn.setEnabled(True)
        self._device_combo.setEnabled(True)
        self._output_format_combo.setEnabled(True)
        self._output_quality_combo.setEnabled(True)
        self._restoration_combo.setEnabled(True)

        if error:
            if "cancelled" in error.lower():
                self._status.showMessage("Processing cancelled")
            else:
                self._status.showMessage(f"Error: {error}")
                QMessageBox.critical(self, "Processing Error", error)
        else:
            self._status.showMessage(f"Split complete — saved {count} tracks to {output_dir}")
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {count} tracks to:\n{output_dir}"
            )

    def closeEvent(self, event):
        self._save_window_state()
        if self._temp_wav_path and os.path.exists(self._temp_wav_path):
            try:
                os.unlink(self._temp_wav_path)
            except OSError:
                pass
        super().closeEvent(event)
