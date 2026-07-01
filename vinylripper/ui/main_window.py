import os
import threading

import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
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
from vinylripper.core.needle_detector import NeedleDetector
from vinylripper.core.recorder import Recorder
from vinylripper.core.splitter import detect_silence_splits
from vinylripper.core.states import RecordingSession, RecordingState
from vinylripper.ui.search_dialog import SearchDialog
from vinylripper.ui.settings_dialog import SettingsDialog
from vinylripper.ui.tabs.check_level_tab import CheckLevelTab
from vinylripper.ui.tabs.cleanup_audio_tab import CleanupAudioTab
from vinylripper.ui.tabs.recording_tab import RecordingTab
from vinylripper.ui.tabs.split_tracks_tab import SplitTracksTab

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
QTabWidget::pane {
    border: 1px solid #3a3a48;
    background-color: #1a1a20;
}
QTabBar::tab {
    background-color: #2a2a35;
    color: #a0a0b0;
    border: 1px solid #3a3a48;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 6px 16px;
    margin-right: 2px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #1a1a20;
    color: #d0d0d8;
    border-bottom: 1px solid #1a1a20;
}
QTabBar::tab:hover:!selected {
    background-color: #353548;
    border-color: #4a4a5a;
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

        # Session — shared state across all tabs
        self._session = RecordingSession()

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

        # Non-blocking calibration
        self._calibration_recorder: Recorder | None = None
        self._calibration_buffer: list[np.ndarray] = []
        self._calibration_timer = QTimer()
        self._calibration_timer.setSingleShot(True)
        self._calibration_timer.timeout.connect(self._finish_calibration)

        # Pre-recording countdown timer (used only before initial recording)
        self._countdown_timer = QTimer()
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._countdown_remaining = 0
        self._pending_recording_data: dict | None = None

        # Flip monitoring recorder — runs while the main recorder is paused,
        # waiting for the needle to drop on the next side
        self._flip_monitor_recorder: Recorder | None = None

        # Grace period after flip — prevents side-end detection from
        # immediately re-triggering while the user is dropping the needle
        self._flip_grace_timer = QTimer()
        self._flip_grace_timer.setSingleShot(True)
        self._flip_grace_timer.timeout.connect(self._end_flip_grace)

        # Needle-down detector (populated by calibration)
        self._needle_detector = NeedleDetector()

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

        # Undo/Redo actions — created early so menus can reference them
        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._undo)
        self._undo_action.setEnabled(False)

        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._redo)
        self._redo_action.setEnabled(False)

        # ── Menu Bar ──────────────────────────────────────────────
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #141418;
                border-bottom: 1px solid #2a2a32;
                padding: 2px;
            }
            QMenuBar::item {
                color: #a0a0b0;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #2a2a35;
                color: #d0d0d8;
            }
            QMenu {
                background-color: #1a1a20;
                border: 1px solid #3a3a48;
                padding: 4px;
            }
            QMenu::item {
                color: #d0d0d8;
                padding: 4px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #2a2a35;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3a3a48;
                margin: 4px 8px;
            }
        """)

        # File menu
        file_menu = menubar.addMenu("File")
        file_open_action = QAction("Open Session...", self)
        file_open_action.setEnabled(False)
        file_menu.addAction(file_open_action)
        file_save_action = QAction("Save Session...", self)
        file_save_action.setEnabled(False)
        file_menu.addAction(file_save_action)
        file_menu.addSeparator()
        self._export_all_action = QAction("Export All", self)
        self._export_all_action.triggered.connect(self._split_recording)
        file_menu.addAction(self._export_all_action)
        self._export_sel_action = QAction("Export Selected", self)
        self._export_sel_action.setEnabled(False)
        file_menu.addAction(self._export_sel_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction(self._undo_action)
        edit_menu.addAction(self._redo_action)
        edit_menu.addSeparator()
        settings_edit_action = QAction("Settings / Preferences...", self)
        settings_edit_action.triggered.connect(self._show_settings)
        edit_menu.addAction(settings_edit_action)

        # View menu — tab navigation
        view_menu = menubar.addMenu("View")
        view_check = QAction("Check Level", self)
        view_check.triggered.connect(lambda: self._tabs.setCurrentIndex(0))
        view_menu.addAction(view_check)
        view_recording = QAction("Recording Options", self)
        view_recording.triggered.connect(lambda: self._tabs.setCurrentIndex(1))
        view_menu.addAction(view_recording)
        view_split = QAction("Split Tracks", self)
        view_split.triggered.connect(lambda: self._tabs.setCurrentIndex(2))
        view_menu.addAction(view_split)
        view_cleanup = QAction("Cleanup Audio", self)
        view_cleanup.triggered.connect(lambda: self._tabs.setCurrentIndex(3))
        view_menu.addAction(view_cleanup)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        cal_action = QAction("Calibrate Needle-Down", self)
        cal_action.triggered.connect(self._start_calibration)
        tools_menu.addAction(cal_action)
        tools_menu.addSeparator()
        tools_settings_action = QAction("Settings...", self)
        tools_settings_action.triggered.connect(self._show_settings)
        tools_menu.addAction(tools_settings_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About VinylRipper", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # ── Toolbar ──────────────────────────────────────────────
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

        toolbar.addAction(self._undo_action)
        toolbar.addAction(self._redo_action)

        toolbar.addSeparator()

        self._settings_action = QAction("Settings", self)
        self._settings_action.triggered.connect(self._show_settings)
        toolbar.addAction(self._settings_action)

        toolbar.addSeparator()

        self._output_format_combo = QComboBox()
        self._output_format_combo.addItems(["FLAC", "MP3", "AIFF"])
        self._output_format_combo.setCurrentText(
            self._config.default_output_format.upper()
        )
        self._output_format_combo.setFixedWidth(100)
        toolbar.addWidget(self._output_format_combo)

        self._output_quality_combo = QComboBox()
        self._output_quality_combo.setFixedWidth(160)
        self._update_quality_options()
        self._output_format_combo.currentTextChanged.connect(
            self._update_quality_options
        )
        toolbar.addWidget(self._output_quality_combo)

        # ── Tab Widget ───────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Tab 0: Check Level
        self._check_tab = CheckLevelTab()
        self._check_tab.set_session(self._session)
        self._check_tab.calibration_requested.connect(self._start_calibration)
        self._check_tab.device_changed.connect(self._on_device_changed)
        self._tabs.addTab(self._check_tab, "Check Level")

        # Tab 1: Recording Options
        self._recording_tab = RecordingTab()
        self._recording_tab.set_session(self._session)
        self._recording_tab.record_toggled.connect(self._toggle_recording)
        self._recording_tab.discogs_search_requested.connect(self._search_discogs)
        self._tabs.addTab(self._recording_tab, "Recording Options")

        # Tab 2: Split Tracks
        self._split_tab = SplitTracksTab()
        self._split_tab.set_session(self._session)
        self._split_tab.split_export_requested.connect(self._split_recording)
        self._split_tab.save_requested.connect(self._save_recording)
        self._split_tab.threshold_slider.valueChanged.connect(
            self._on_threshold_changed
        )
        self._split_tab.gap_slider.valueChanged.connect(self._on_duration_changed)
        self._split_tab.waveform.markers_changed.connect(self._on_markers_changed)
        self._tabs.addTab(self._split_tab, "Split Tracks")

        # Tab 3: Cleanup Audio
        self._cleanup_tab = CleanupAudioTab()
        self._cleanup_tab.process_requested.connect(self._process_cleanup)
        self._cleanup_tab.preview_btn.clicked.connect(self._play_before_cleanup)
        self._cleanup_tab.preview_after_btn.clicked.connect(self._play_after_cleanup)
        self._tabs.addTab(self._cleanup_tab, "Cleanup Audio")

        layout.addWidget(self._tabs, 1)

        # ── Backward-compat widget references ────────────────────
        self._device_combo = self._check_tab.device_combo
        self._waveform = self._split_tab.waveform  # main waveform for undo/redo/split

        # ── Status Bar ───────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    # ── Signal wiring helpers ──────────────────────────────────

    def _on_device_changed(self, device_idx: int):
        """Handle device selection change from CheckLevelTab."""
        self._session.device_id = device_idx

    def _start_calibration(self):
        """Start non-blocking calibration of noise floor for needle-down detection."""
        idx = self._check_tab.device_combo.currentData()
        devices = getattr(self._check_tab, "_devices", None)
        if devices is None or idx is None or idx >= len(devices):
            self._status.showMessage("No valid input device selected")
            return

        self._session.state = RecordingState.CALIBRATING
        self._update_tabs_state()
        device_info = devices[idx]
        self._status.showMessage("Calibrating noise floor... (5 seconds)")

        sr = int(device_info["default_samplerate"])
        self._calibration_recorder = Recorder(
            device=str(device_info["name"]),
            samplerate=sr,
            channels=min(2, device_info["max_input_channels"]),
        )
        self._calibration_buffer = []
        self._session.samplerate = sr
        self._calibration_recorder.start()
        self._calibration_timer.start(5000)  # 5 seconds

    def _finish_calibration(self):
        """Finish calibration: compute noise floor from buffered audio."""
        cal_recorder = self._calibration_recorder
        self._calibration_recorder = None

        if cal_recorder:
            cal_recorder.stop()

        if self._calibration_buffer:
            data = np.concatenate(self._calibration_buffer)
        else:
            data = None

        if data is not None and len(data) > 0:
            sr = self._session.samplerate or 44100
            detector = NeedleDetector(samplerate=sr)
            detector.calibrate(data)
            self._session.noise_floor_rms = detector.noise_floor_rms
            self._session.noise_floor_peak = detector.noise_floor_peak
            self._session.calibrated = True
            self._needle_detector = detector
            self._session.state = RecordingState.CALIBRATED
            self._check_tab.set_session(self._session)
            self._recording_tab.set_session(self._session)
            self._status.showMessage(
                "Calibration complete — drop the needle to auto-start"
            )
            self._calibration_buffer = []

            # Start monitoring for needle drop
            if cal_recorder:
                self._recorder = Recorder(
                    device=cal_recorder.device,
                    samplerate=sr,
                    channels=cal_recorder.channels,
                )
                self._recorder.start()
        else:
            self._session.state = RecordingState.IDLE
            self._status.showMessage("Calibration failed — no audio data")

        self._update_tabs_state()

    def _update_tabs_state(self):
        """Push current session state to all tabs."""
        state = self._session.state
        self._check_tab.update_state(state)
        self._recording_tab.update_state(state)
        self._split_tab.update_state(state)

        # Enable cleanup tab buttons when recorded audio is available
        has_data = (
            self._recorded_data is not None
            and len(self._recorded_data) > 0
            and state == RecordingState.STOPPED
        )
        self._cleanup_tab.preview_btn.setEnabled(has_data)
        self._cleanup_tab.preview_after_btn.setEnabled(has_data)
        self._cleanup_tab.process_btn.setEnabled(has_data)

    def _get_restoration_level(self) -> int:
        """Derive restoration level from CleanupAudioTab settings.

        Returns:
            0 = None, 1 = Highpass only, 2 = Highpass + Declick
        """
        settings = self._cleanup_tab.get_settings()
        hp = settings.get("highpass", {}).get("enabled", False)
        dc = settings.get("declick", {}).get("enabled", False)
        if hp and dc:
            return 2
        if hp:
            return 1
        return 0

    # ── Cleanup Audio handlers ────────────────────────────────

    def _play_before_cleanup(self):
        """Play a short segment of the original (unprocessed) recording."""
        if self._recorded_data is None or len(self._recorded_data) == 0:
            return
        import sounddevice as sd

        sr = self._session.samplerate or 44100
        segment_dur = 5  # seconds
        n_samples = min(int(sr * segment_dur), len(self._recorded_data))
        segment = self._recorded_data[:n_samples]
        sd.play(segment, sr)
        self._status.showMessage("Playing original audio...")

    def _play_after_cleanup(self):
        """Play a short segment of the recording with restoration applied."""
        if self._recorded_data is None or len(self._recorded_data) == 0:
            return
        import sounddevice as sd
        import soundfile as sf

        sr = self._session.samplerate or 44100
        segment_dur = 5  # seconds
        n_samples = min(int(sr * segment_dur), len(self._recorded_data))
        segment = self._recorded_data[:n_samples]

        import tempfile

        # Write the segment to a temp file
        in_path = tempfile.mktemp(suffix=".wav")
        out_path = tempfile.mktemp(suffix=".wav")
        try:
            sf.write(in_path, segment, sr)
            settings = self._cleanup_tab.get_settings()
            from vinylripper.core.audio_processor import apply_restoration

            if apply_restoration(in_path, out_path, settings, samplerate=sr):
                processed_data, _ = sf.read(out_path, dtype="float32")
                sd.play(processed_data, sr)
                self._status.showMessage("Playing processed audio...")
            else:
                self._status.showMessage("Processing failed — check FFmpeg")
        finally:
            import os

            for p in (in_path, out_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def _process_cleanup(self):
        """Apply restoration settings to the full recording in-place."""
        if self._recorded_data is None or len(self._recorded_data) == 0:
            return
        import soundfile as sf

        sr = self._session.samplerate or 44100
        self._session.state = RecordingState.PROCESSING
        self._update_tabs_state()
        self._status.showMessage("Processing audio...")

        import tempfile

        in_path = tempfile.mktemp(suffix=".wav")
        out_path = tempfile.mktemp(suffix=".wav")
        try:
            sf.write(in_path, self._recorded_data, sr)
            settings = self._cleanup_tab.get_settings()
            from vinylripper.core.audio_processor import apply_restoration

            if apply_restoration(in_path, out_path, settings, samplerate=sr):
                processed_data, _ = sf.read(out_path, dtype="float32")
                self._recorded_data = processed_data
                self._session.recorded_data = processed_data
                self._session.state = RecordingState.STOPPED

                # Reload into SplitTracksTab waveform
                self._split_tab.set_full_audio(processed_data, sr)

                # Re-run split preview
                if self._album_metadata and self._album_metadata.tracklist:
                    self._update_split_preview()
                    self._update_track_labels()
                else:
                    self._split_tab.waveform.set_split_markers([])

                dur = len(processed_data) / sr
                self._status.showMessage(
                    f"Processing complete — {dur:.1f}s processed"
                )
            else:
                self._session.state = RecordingState.STOPPED
                self._status.showMessage("Processing failed — check FFmpeg")
        except Exception as e:
            self._session.state = RecordingState.STOPPED
            self._status.showMessage(f"Processing error: {e}")
        finally:
            import os

            for p in (in_path, out_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            self._update_tabs_state()

    def _show_about(self):
        """Show About dialog."""
        QMessageBox.about(
            self,
            "About VinylRipper",
            "VinylRipper v1.0\n\n"
            "A desktop application for digitizing vinyl records.\n\n"
            "Record from your turntable, automatically split tracks,\n"
            "look up album metadata from Discogs, and export as\n"
            "tagged FLAC/MP3/AIFF files.",
        )

    # ── Device population ──────────────────────────────────────

    def _populate_devices(self):
        devices = self._recorder.list_input_devices()
        self._check_tab.populate_devices(devices)
        # Backward compat reference
        self._device_combo = self._check_tab.device_combo

    # ── Timer ──────────────────────────────────────────────────

    def _setup_timer(self):
        self._timer = QTimer()
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._poll_audio)
        self._timer.start()

    # ── Shortcuts ──────────────────────────────────────────────

    def _setup_shortcuts(self):
        # Undo/Redo shortcuts
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self._undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self._redo)

        # Delete key to remove selected marker
        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        delete_shortcut.activated.connect(self._delete_selected_marker)

    # ── Window state ───────────────────────────────────────────

    def _load_window_state(self):
        pass

    def _save_window_state(self):
        self._config.set("window_width", self.width())
        self._config.set("window_height", self.height())
        self._config.save()

    # ── Quality options ────────────────────────────────────────

    def _update_quality_options(self):
        fmt = self._output_format_combo.currentText().lower()
        self._output_quality_combo.clear()
        if fmt == "flac":
            self._output_quality_combo.addItems(
                [f"Compression {i} (0=fast, 8=best)" for i in range(9)]
            )
            self._output_quality_combo.setCurrentIndex(
                self._config.default_flac_compression
            )
        elif fmt == "mp3":
            self._output_quality_combo.addItems(
                [
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
                ]
            )
            self._output_quality_combo.setCurrentText(
                f"VBR {self._config.default_mp3_quality} (~245 kbps, best)"
                if self._config.default_mp3_quality == "0"
                else f"VBR {self._config.default_mp3_quality}"
            )
        elif fmt == "aiff":
            self._output_quality_combo.addItems(
                ["16-bit PCM", "24-bit PCM", "32-bit Float"]
            )
            self._output_quality_combo.setCurrentIndex(0)

    # ── Undo / Redo / Marker operations ────────────────────────

    def _undo(self):
        if self._split_tab.waveform.undo():
            self._update_undo_redo_actions()
            self._status.showMessage("Undo", 2000)

    def _redo(self):
        if self._split_tab.waveform.redo():
            self._update_undo_redo_actions()
            self._status.showMessage("Redo", 2000)

    def _update_undo_redo_actions(self):
        self._undo_action.setEnabled(self._split_tab.waveform.can_undo())
        self._redo_action.setEnabled(self._split_tab.waveform.can_redo())

    def _delete_selected_marker(self):
        """Delete the currently hovered split marker."""
        idx = self._split_tab.waveform.hovered_marker_index()
        if idx >= 0:
            self._split_tab.waveform.remove_marker_at_index(idx)
            self._status.showMessage("Marker deleted", 2000)

    # ── Settings ───────────────────────────────────────────────

    def _show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self._split_tab.threshold_slider.setValue(
                int(-self._config.silence_threshold_db)
            )
            self._split_tab.gap_slider.setValue(
                int(self._config.min_silence_duration * 1000)
            )
            self._output_format_combo.setCurrentText(
                self._config.default_output_format.upper()
            )
            self._update_quality_options()
            self._status.showMessage("Settings saved", 2000)

    # ── Audio polling ──────────────────────────────────────────

    def _poll_audio(self):
        # Flip monitoring — main recorder is paused, waiting for needle drop
        if self._flip_monitor_recorder is not None:
            for data in self._flip_monitor_recorder.drain():
                if data.ndim > 1:
                    mono = data.mean(axis=1)
                else:
                    mono = data
                rms = np.sqrt(np.mean(mono**2))
                # -35 dBFS threshold (same as _try_resume_recording used)
                if rms > 10 ** (-35 / 20):
                    self._on_flip_detected()
                    return
            return

        if self._session.state == RecordingState.CALIBRATING:
            if self._calibration_recorder:
                for data in self._calibration_recorder.drain():
                    self._calibration_buffer.append(data)
            return

        if self._session.state == RecordingState.CALIBRATED:
            # Needle-down detection: wait for signal
            if self._recorder:
                for data in self._recorder.drain():
                    if self._needle_detector.is_signal_detected(
                        data, threshold_multiplier=3.0
                    ):
                        self._auto_start_recording()
                        return
            return

        if not self._recording:
            return
        for data in self._recorder.drain():
            self._check_tab.waveform.enqueue(data)
            self._session.accumulate_audio(self._session.current_side, data)

    # ── Recording control ──────────────────────────────────────

    def _toggle_recording(self):
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        """Start recording workflow: search album, then begin countdown."""
        idx = self._check_tab.device_combo.currentData()
        devices = getattr(self._check_tab, "_devices", None)
        if devices is None or idx is None or idx >= len(devices):
            self._status.showMessage("No valid input device selected")
            return

        dialog = SearchDialog(self)
        if dialog.exec() != SearchDialog.DialogCode.Accepted:
            return

        self._album_metadata = dialog.album_metadata
        if self._album_metadata and self._album_metadata.artist:
            self._recording_tab.set_metadata_display(
                self._album_metadata.artist, self._album_metadata.title
            )
            self._recording_tab.set_tracklist(
                self._album_metadata.tracklist,
                getattr(self._album_metadata, "side_tracklist", None),
            )
        else:
            self._recording_tab.set_metadata_display("", "")

        # Also update session metadata
        self._session.metadata = self._album_metadata

        # Stop monitoring recorder to prevent needle-detect from
        # hijacking the manual recording countdown
        if self._session.state == RecordingState.CALIBRATED and self._recorder:
            self._recorder.stop()
            self._recorder = None

        device_info = devices[idx]
        sr = int(device_info["default_samplerate"])

        # Store pending recording params for after countdown
        self._pending_recording_data = {
            "device_idx": idx,
            "device_name": str(device_info["name"]),
            "samplerate": sr,
            "channels": min(2, device_info["max_input_channels"]),
        }

        # Start 3-second countdown
        self._countdown_remaining = 3
        self._recording_tab.show_countdown(self._countdown_remaining)
        self._countdown_timer.start()
        self._status.showMessage(f"Starting in {self._countdown_remaining}...")

    def _countdown_tick(self):
        """Handle pre-recording countdown timer."""
        self._countdown_remaining -= 1
        if self._countdown_remaining > 0:
            self._recording_tab.show_countdown(self._countdown_remaining)
            self._status.showMessage(f"Starting in {self._countdown_remaining}...")
        else:
            self._countdown_timer.stop()
            self._recording_tab.hide_countdown()
            if self._pending_recording_data:
                self._begin_recording()

    def _begin_recording(self):
        """Actually start recording after countdown completes."""
        if not self._pending_recording_data:
            return
        params = self._pending_recording_data
        self._pending_recording_data = None

        device_name = params.get("device_name")
        sr = params["samplerate"]
        ch = params["channels"]

        # Stop any leftover monitoring recorder before creating recording one
        if self._recorder:
            self._recorder.stop()

        self._recorder = Recorder(
            device=device_name, samplerate=sr, channels=ch
        )

        import tempfile

        self._temp_wav_path = tempfile.mktemp(suffix=".wav")
        self._session.temp_wav_path = self._temp_wav_path

        self._recorder.start()
        self._recording = True
        self._side = 1
        self._side_check_timer.start()

        self._session.state = RecordingState.RECORDING
        self._session.samplerate = sr
        self._session.recorded_data = None
        self._session.markers = []
        self._session.current_side = 1

        # Live waveform on CheckLevelTab
        self._check_tab.waveform.set_samplerate(sr)
        self._check_tab.waveform.set_recording(True)
        self._check_tab.waveform.clear_review()
        self._check_tab.waveform.reset()

        # Clear split waveform for fresh recording
        self._split_tab.waveform.clear_undo_stack()
        self._split_tab.waveform.clear_review()
        self._session.clear_side_data()

        # Update UI controls
        self._recording_tab.record_btn.setText("Stop")
        self._split_tab.save_btn.setEnabled(False)
        self._split_tab.export_btn.setEnabled(False)
        self._check_tab.device_combo.setEnabled(False)

        self._update_undo_redo_actions()
        self._update_tabs_state()
        self._status.showMessage("Recording...")

    def _search_discogs(self):
        """Open Discogs search dialog and store selected album metadata."""
        from vinylripper.ui.search_dialog import SearchDialog

        dialog = SearchDialog(self)
        if dialog.exec() != SearchDialog.DialogCode.Accepted:
            return

        self._album_metadata = dialog.album_metadata
        if self._album_metadata and self._album_metadata.artist:
            self._recording_tab.set_metadata_display(
                self._album_metadata.artist, self._album_metadata.title
            )
            self._recording_tab.set_tracklist(
                self._album_metadata.tracklist,
                getattr(self._album_metadata, "side_tracklist", None),
            )
        else:
            self._recording_tab.set_metadata_display("", "")

        self._session.metadata = self._album_metadata
        self._status.showMessage(
            f"Album set: {self._album_metadata.artist} — {self._album_metadata.title}"
            if self._album_metadata
            else "No album selected"
        )

    def _auto_start_recording(self):
        """Start recording automatically when needle-drop detected.

        Stops the monitoring recorder to prevent re-triggering during the
        countdown — otherwise _poll_audio keeps detecting signal and
        restarts the countdown every 30ms, so it never reaches zero.
        """
        idx = self._check_tab.device_combo.currentData()
        devices = getattr(self._check_tab, "_devices", None)
        if devices is None or idx is None or idx >= len(devices):
            self._status.showMessage("Needle detected but no device selected")
            return
        device_info = devices[idx]
        sr = int(device_info["default_samplerate"])
        ch = min(2, device_info["max_input_channels"])

        self._pending_recording_data = {
            "device_idx": idx,
            "device_name": str(device_info["name"]),
            "samplerate": sr,
            "channels": ch,
        }

        # Stop monitoring recorder to prevent re-triggering during countdown
        if self._recorder:
            self._recorder.stop()
        self._recorder = None

        # Needle-detected auto-start uses a shorter countdown
        self._countdown_remaining = 2
        self._recording_tab.show_countdown(self._countdown_remaining)
        self._countdown_timer.start()
        self._status.showMessage("Needle detected — starting...")

    def _stop_recording(self):
        self._side_check_timer.stop()
        self._resume_timer.stop()
        self._countdown_timer.stop()
        self._recording_tab.hide_countdown()
        self._stop_flip_monitoring()

        # Drain remaining audio from recorder into session
        for chunk in self._recorder.drain():
            self._session.accumulate_audio(self._session.current_side, chunk)

        # Stop recorder (close stream — data is in session)
        self._recorder.stop()
        self._recording = False
        self._side = 1

        # CheckLevelTab waveform stops live display
        self._check_tab.waveform.set_recording(False)

        self._recording_tab.record_btn.setText("Record")
        self._check_tab.device_combo.setEnabled(True)

        # Get finalized audio with side gap handling
        data = self._session.finalize_audio()

        if data is not None and len(data) > 0:
            self._recorded_data = data
            self._session.recorded_data = data
            self._session.state = RecordingState.STOPPED

            self._split_tab.save_btn.setEnabled(True)
            sr = self._recorder.samplerate

            import soundfile as sf

            if self._temp_wav_path:
                sf.write(self._temp_wav_path, data, sr)

            # Load audio into SplitTracksTab waveform
            self._split_tab.set_full_audio(data, sr)

            has_tracks = bool(self._album_metadata and self._album_metadata.tracklist)
            self._split_tab.export_btn.setEnabled(has_tracks)
            if has_tracks:
                self._update_split_preview()
                self._update_track_labels()
            else:
                self._split_tab.update_split_status(
                    "Split & save available after Discogs search"
                )
            dur = len(data) / sr
            self._status.showMessage(f"Recorded {dur:.1f}s — ready to save")
        else:
            self._recorded_data = None
            self._session.recorded_data = None
            self._session.state = RecordingState.IDLE
            self._split_tab.save_btn.setEnabled(False)
            self._split_tab.export_btn.setEnabled(False)
            self._status.showMessage("No audio recorded")

        self._update_tabs_state()

    # ── Side detection ─────────────────────────────────────────

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
            chunk = (
                mono[-(i + 1) * window : len(mono) - i * window]
                if i
                else mono[-window:]
            )
            rms = np.sqrt(np.mean(chunk**2))
            if rms < threshold:
                silent += 1
            else:
                silent = 0

        if silent >= 8:
            self._on_side_finished()

    def _on_side_finished(self):
        self._recorder.pause()
        self._side_check_timer.stop()
        self._resume_timer.stop()
        self._check_tab.waveform.set_recording(False)

        self._session.state = RecordingState.PAUSED
        self._update_tabs_state()

        if self._side < self._session.total_sides:
            # Wait for needle drop on the next side — no countdown
            self._start_flip_monitoring()
            self._status.showMessage(
                f"Side {self._session.side_letter()} done — flip record, "
                f"next side will auto-start"
            )
        else:
            # All sides done — finalize
            self._finish_recording()

    def _start_flip_monitoring(self):
        """Start a monitoring recorder to detect needle drop for the next side.

        Runs a lightweight recorder while the main recorder is paused.
        When audio is detected (needle drop), _on_flip_detected is called.
        """
        sr = (
            self._session.samplerate
            or getattr(self._recorder, "samplerate", 44100)
        )
        device = getattr(self._recorder, "device", None)
        ch = min(getattr(self._recorder, "channels", 2), 1)

        self._flip_monitor_recorder = Recorder(
            device=device, samplerate=sr, channels=ch
        )
        self._flip_monitor_recorder.start()

    def _stop_flip_monitoring(self):
        """Stop and discard the flip monitoring recorder."""
        if self._flip_monitor_recorder:
            self._flip_monitor_recorder.stop()
            self._flip_monitor_recorder = None

    def _on_flip_detected(self):
        """Needle dropped — resume the main recorder for the next side."""
        self._stop_flip_monitoring()

        self._side += 1
        self._recorder.resume()
        self._check_tab.waveform.set_recording(True)

        self._session.current_side = self._side
        self._session.state = RecordingState.RECORDING
        self._update_tabs_state()

        # Don't start side-end detection yet — give time for the needle
        # to settle. The grace timer will start _side_check_timer later.
        self._flip_grace_timer.start(12000)  # 12-second grace period
        self._status.showMessage(f"Recording Side {self._session.side_letter()}...")

    def _finish_recording(self):
        """Finalize multi-side recording."""
        self._side_check_timer.stop()
        self._resume_timer.stop()
        self._countdown_timer.stop()
        self._flip_grace_timer.stop()
        self._stop_flip_monitoring()
        self._recording_tab.hide_countdown()

        # Drain remaining audio from recorder into session
        for chunk in self._recorder.drain():
            self._session.accumulate_audio(self._session.current_side, chunk)

        # Stop recorder (close stream — data is in session)
        self._recorder.stop()
        self._recording = False
        self._side = 1

        self._check_tab.waveform.set_recording(False)
        self._recording_tab.record_btn.setText("Record")
        self._check_tab.device_combo.setEnabled(True)

        # Get finalized audio with side gap handling
        data = self._session.finalize_audio()

        if data is not None and len(data) > 0:
            self._recorded_data = data
            self._session.recorded_data = data
            self._session.state = RecordingState.STOPPED

            self._split_tab.save_btn.setEnabled(True)
            sr = self._recorder.samplerate

            import soundfile as sf

            if self._temp_wav_path:
                sf.write(self._temp_wav_path, data, sr)

            # Load audio into SplitTracksTab waveform
            self._split_tab.set_full_audio(data, sr)

            has_tracks = bool(self._album_metadata and self._album_metadata.tracklist)
            self._split_tab.export_btn.setEnabled(has_tracks)
            if has_tracks:
                self._update_split_preview()
                self._update_track_labels()
            else:
                self._split_tab.update_split_status(
                    "Split & save available after Discogs search"
                )
            dur = len(data) / sr
            self._status.showMessage(f"Recorded {dur:.1f}s — ready to save")
        else:
            self._recorded_data = None
            self._session.recorded_data = None
            self._session.state = RecordingState.IDLE
            self._split_tab.save_btn.setEnabled(False)
            self._split_tab.export_btn.setEnabled(False)
            self._status.showMessage("No audio recorded")

        self._update_tabs_state()

    def _end_flip_grace(self):
        """End the post-flip grace period and enable side-end detection."""
        self._side_check_timer.start()


    # ── Split preview / markers ────────────────────────────────

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
        self._split_tab.update_split_status(label)
        self._update_track_labels()

    def _update_split_preview(self):
        if self._recorded_data is None:
            return
        threshold_db = -(self._split_tab.threshold_slider.value())
        min_silence_ms = self._split_tab.gap_slider.value()
        try:
            sr = self._recorder.samplerate
            points = detect_silence_splits(
                self._recorded_data,
                sr,
                threshold_db=threshold_db,
                min_silence_ms=min_silence_ms,
            )
            self._split_tab.set_split_markers(points)
            self._update_track_labels()
            n = len(points) + 1
            label = f"Detected {n} tracks" if points else "No gaps detected"
            track_count = (
                len(self._album_metadata.tracklist) if self._album_metadata else 0
            )
            if track_count and n != track_count:
                label += f"  ({track_count} in metadata)"
            self._split_tab.update_split_status(label)
        except Exception:
            self._split_tab.update_split_status("")

    def _update_track_labels(self):
        """Update track label overlay based on split markers and metadata."""
        if not self._album_metadata or not self._album_metadata.tracklist:
            self._split_tab.waveform.set_track_labels([])
            return

        split_points = self._split_tab.waveform.get_split_markers()
        positions = self._album_metadata.get_vinyl_positions()

        labels: list[tuple[int, str]] = []
        for i, pos in enumerate(positions):
            track = (
                self._album_metadata.tracklist[i]
                if i < len(self._album_metadata.tracklist)
                else {}
            )
            title = track.get("title", "")
            label_text = f"{pos}  {title}" if title else pos

            if i < len(split_points):
                labels.append((split_points[i], label_text))
            else:
                # Last track — place at end of audio
                total = (
                    len(self._recorded_data) if self._recorded_data is not None else 0
                )
                labels.append((total, label_text))

        self._split_tab.waveform.set_track_labels(labels)

    # ── Split & Export ─────────────────────────────────────────

    def _split_recording(self):
        if self._recorded_data is None or not self._temp_wav_path:
            return

        split_points = self._split_tab.get_split_points()
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

        self._split_tab.export_btn.setEnabled(False)
        self._split_tab.save_btn.setEnabled(False)
        self._recording_tab.record_btn.setEnabled(False)
        self._check_tab.device_combo.setEnabled(False)
        self._output_format_combo.setEnabled(False)
        self._output_quality_combo.setEnabled(False)
        self._status.showMessage("Processing tracks...")

        self._session.state = RecordingState.PROCESSING
        self._update_tabs_state()

        self._cancel_event.clear()

        # Prepare track metadata
        track_metadata = []
        if self._album_metadata:
            for i in range(n_detected):
                track_metadata.append(self._album_metadata.get_track_metadata(i))
        else:
            for i in range(n_detected):
                track_metadata.append(
                    {
                        "position": str(i + 1),
                        "title": f"Track {i + 1}",
                        "artist": "",
                        "album": "",
                    }
                )

        # Get output format and quality
        fmt = self._output_format_combo.currentText().lower()
        quality_text = self._output_quality_combo.currentText()

        if fmt == "flac":
            flac_compression = (
                int(quality_text.split()[1].split("(")[0])
                if "Compression" in quality_text
                else self._config.default_flac_compression
            )
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

        restoration_level = self._get_restoration_level()

        # Run processing in background thread
        self._processing_thread = threading.Thread(
            target=self._process_tracks_thread,
            args=(
                self._temp_wav_path,
                dir_path,
                split_points_sec,
                track_metadata,
                fmt,
                flac_compression,
                mp3_quality,
                restoration_level,
            ),
            daemon=True,
        )
        self._processing_thread.start()

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
            self,
            "Save Audio",
            f"recording.{fmt}",
            filters.get(fmt, "FLAC (*.flac)"),
        )
        if not path:
            return

        fmt = self._output_format_combo.currentText().lower()
        quality_text = self._output_quality_combo.currentText()

        if fmt == "flac":
            flac_compression = (
                int(quality_text.split()[1].split("(")[0])
                if "Compression" in quality_text
                else self._config.default_flac_compression
            )
        elif fmt == "mp3":
            if "VBR" in quality_text:
                mp3_quality = quality_text.split("VBR")[1].split("(")[0].strip()
            else:
                mp3_quality = self._config.default_mp3_quality
        else:
            flac_compression = 8
            mp3_quality = "0"

        restoration_level = self._get_restoration_level()

        self._split_tab.save_btn.setEnabled(False)
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
                    embed_cover_art(
                        path,
                        self._album_metadata.cover_data,
                        self._album_metadata.cover_mime,
                    )
                self._save_finished.emit(
                    success,
                    path,
                    None if success else "Conversion failed",
                )
            except Exception as e:
                self._save_finished.emit(False, "", str(e))

        threading.Thread(target=convert_thread, daemon=True).start()

    def _on_save_finished(self, success, path, error):
        self._split_tab.save_btn.setEnabled(True)
        if success:
            self._status.showMessage(f"Saved: {path}")
        else:
            self._status.showMessage(f"Save failed: {error}")
            QMessageBox.critical(self, "Save Error", error or "Unknown error")

    def _process_tracks_thread(
        self,
        input_file,
        output_dir,
        split_points,
        track_metadata,
        fmt,
        flac_compression,
        mp3_quality,
        restoration_level,
    ):
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

            if self._album_metadata and self._album_metadata.cover_data:
                for f in output_files:
                    embed_cover_art(
                        f,
                        self._album_metadata.cover_data,
                        self._album_metadata.cover_mime,
                    )

            self._processing_finished.emit(len(output_files), output_dir, None)
        except Exception as e:
            self._processing_finished.emit(0, "", str(e))

    def _on_track_progress(self, current, total, filepath):
        self._status.showMessage(f"Processing track {current}/{total}...")

    def _on_processing_finished(self, count, output_dir, error):
        self._split_tab.export_btn.setEnabled(True)
        self._split_tab.save_btn.setEnabled(True)
        self._recording_tab.record_btn.setEnabled(True)
        self._check_tab.device_combo.setEnabled(True)
        self._output_format_combo.setEnabled(True)
        self._output_quality_combo.setEnabled(True)

        self._session.state = RecordingState.STOPPED
        self._update_tabs_state()

        if error:
            if "cancelled" in error.lower():
                self._status.showMessage("Processing cancelled")
            else:
                self._status.showMessage(f"Error: {error}")
                QMessageBox.critical(self, "Processing Error", error)
        else:
            self._status.showMessage(
                f"Split complete — saved {count} tracks to {output_dir}"
            )
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {count} tracks to:\n{output_dir}",
            )

    def closeEvent(self, event):
        self._save_window_state()
        if self._temp_wav_path and os.path.exists(self._temp_wav_path):
            try:
                os.unlink(self._temp_wav_path)
            except OSError:
                pass
        super().closeEvent(event)
