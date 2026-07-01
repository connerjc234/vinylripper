"""Check Level tab — live waveform display, input device selection, needle calibration."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vinylripper.core.states import RecordingState
from vinylripper.ui.waveform_widget import WaveformWidget


class CheckLevelTab(QWidget):
    """Live waveform monitoring, device selection, and needle-down calibration."""

    calibration_requested = pyqtSignal()
    device_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Waveform
        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform, 1)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        device_label = QLabel("Input Device")
        controls.addWidget(device_label)

        self.device_combo = QComboBox()
        self.device_combo.setFixedHeight(30)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        controls.addWidget(self.device_combo, 1)

        # Level indicator
        self.level_label = QLabel("— dBFS")
        self.level_label.setStyleSheet("color: #888; font-size: 11px;")
        controls.addWidget(self.level_label)

        controls.addSpacing(12)

        # Calibration
        self.calibrate_btn = QPushButton("Calibrate Noise Floor")
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.clicked.connect(self.calibration_requested.emit)
        controls.addWidget(self.calibrate_btn)

        self.cal_status = QLabel("Needle Calibration: —")
        self.cal_status.setStyleSheet("color: #666; font-size: 11px;")
        controls.addWidget(self.cal_status)

        layout.addLayout(controls)

    def set_session(self, session):
        """Connect this tab to the shared RecordingSession."""
        self._session = session
        if session:
            self.calibrate_btn.setEnabled(True)
            if session.calibrated:
                self.cal_status.setText(
                    f"Needle Calibration: {session.side_letter()}"
                    f" ({session.noise_floor_rms:.6f})"
                )
                self.cal_status.setStyleSheet("color: #4caf50; font-size: 11px;")

    def populate_devices(self, devices: list[dict]):
        """Fill device combo with available input devices."""
        self._devices = devices
        self.device_combo.clear()
        default = None
        for i, d in enumerate(devices):
            name = d["name"]
            ch = d["max_input_channels"]
            self.device_combo.addItem(f"{name}  ({ch} ch)", i)
            if d.get("default"):
                default = i
        if default is not None:
            self.device_combo.setCurrentIndex(default)

    def _on_device_changed(self, idx):
        if idx >= 0:
            self.device_changed.emit(self.device_combo.currentData())

    def update_level(self, db: float):
        """Update the level indicator with current dBFS."""
        self.level_label.setText(f"{db:.1f} dBFS")
        if db > -6:
            color = "#ff4444"
        elif db > -18:
            color = "#ffaa00"
        else:
            color = "#888"
        self.level_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def update_state(self, state: RecordingState):
        """Update UI to reflect current recording state."""
        is_live = state in (
            RecordingState.CALIBRATING,
            RecordingState.RECORDING,
            RecordingState.PAUSED,
            RecordingState.FLIP_COUNTDOWN,
        )
        self.waveform.set_recording(is_live)
        self.device_combo.setEnabled(
            state == RecordingState.IDLE
        )

    def clear_calibration(self):
        """Reset calibration display."""
        self.cal_status.setText("Needle Calibration: —")
        self.cal_status.setStyleSheet("color: #666; font-size: 11px;")
        self.level_label.setText("— dBFS")
        self.level_label.setStyleSheet("color: #888; font-size: 11px;")
