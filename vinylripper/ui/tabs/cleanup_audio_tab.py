"""Cleanup Audio tab — restoration controls for de-clicking, de-noising, and filtering."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class CleanupAudioTab(QWidget):
    """Audio restoration controls with per-filter fine-tuning."""

    settings_changed = pyqtSignal(dict)
    process_requested = pyqtSignal()
    """Emitted when the user clicks 'Process Full Recording'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Preset selector
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(
            ["None", "Light (minimal)", "Standard", "Aggressive"]
        )
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        preset_row.addWidget(self.preset_combo)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        # Highpass filter
        hp_group = QGroupBox("Rumble Filter (Highpass)")
        hp_layout = QVBoxLayout(hp_group)

        hp_toggle_row = QHBoxLayout()
        self.hp_enable = QCheckBox("Enable")
        self.hp_enable.setChecked(False)
        self.hp_enable.stateChanged.connect(self._emit_settings)
        hp_toggle_row.addWidget(self.hp_enable)
        hp_layout.addLayout(hp_toggle_row)

        hp_freq_row = QHBoxLayout()
        hp_freq_row.addWidget(QLabel("Cutoff frequency:"))
        self.hp_freq = QSpinBox()
        self.hp_freq.setRange(20, 200)
        self.hp_freq.setValue(30)
        self.hp_freq.setSuffix(" Hz")
        self.hp_freq.setEnabled(False)
        self.hp_enable.toggled.connect(self.hp_freq.setEnabled)
        self.hp_freq.valueChanged.connect(self._emit_settings)
        hp_freq_row.addWidget(self.hp_freq)
        hp_freq_row.addStretch()
        hp_layout.addLayout(hp_freq_row)

        hp_info = QLabel("Removes subsonic rumble and turntable hum")
        hp_info.setStyleSheet("color: #888; font-size: 10px;")
        hp_layout.addWidget(hp_info)

        layout.addWidget(hp_group)

        # Declick filter
        dc_group = QGroupBox("De-Clicker")
        dc_layout = QVBoxLayout(dc_group)

        dc_toggle_row = QHBoxLayout()
        self.dc_enable = QCheckBox("Enable")
        self.dc_enable.setChecked(False)
        self.dc_enable.stateChanged.connect(self._emit_settings)
        dc_toggle_row.addWidget(self.dc_enable)
        dc_layout.addLayout(dc_toggle_row)

        dc_strength_row = QHBoxLayout()
        dc_strength_row.addWidget(QLabel("Strength:"))
        self.dc_strength = QSlider(Qt.Orientation.Horizontal)
        self.dc_strength.setRange(0, 100)
        self.dc_strength.setValue(50)
        self.dc_strength.setEnabled(False)
        self.dc_enable.toggled.connect(self.dc_strength.setEnabled)
        self.dc_strength.valueChanged.connect(self._emit_settings)
        dc_strength_row.addWidget(self.dc_strength, 1)
        self.dc_value_label = QLabel("50%")
        self.dc_value_label.setStyleSheet("color: #888; font-size: 10px;")
        self.dc_strength.valueChanged.connect(
            lambda v: self.dc_value_label.setText(f"{v}%")
        )
        dc_strength_row.addWidget(self.dc_value_label)
        dc_layout.addLayout(dc_strength_row)

        dc_info = QLabel("Removes clicks and pops from surface noise")
        dc_info.setStyleSheet("color: #888; font-size: 10px;")
        dc_layout.addWidget(dc_info)

        layout.addWidget(dc_group)

        # Denoise filter
        dn_group = QGroupBox("Noise Reduction")
        dn_layout = QVBoxLayout(dn_group)

        dn_toggle_row = QHBoxLayout()
        self.dn_enable = QCheckBox("Enable")
        self.dn_enable.setChecked(False)
        self.dn_enable.stateChanged.connect(self._emit_settings)
        dn_toggle_row.addWidget(self.dn_enable)
        dn_layout.addLayout(dn_toggle_row)

        dn_strength_row = QHBoxLayout()
        dn_strength_row.addWidget(QLabel("Strength:"))
        self.dn_strength = QSlider(Qt.Orientation.Horizontal)
        self.dn_strength.setRange(0, 100)
        self.dn_strength.setValue(30)
        self.dn_strength.setEnabled(False)
        self.dn_enable.toggled.connect(self.dn_strength.setEnabled)
        self.dn_strength.valueChanged.connect(self._emit_settings)
        dn_strength_row.addWidget(self.dn_strength, 1)
        self.dn_value_label = QLabel("30%")
        self.dn_value_label.setStyleSheet("color: #888; font-size: 10px;")
        self.dn_strength.valueChanged.connect(
            lambda v: self.dn_value_label.setText(f"{v}%")
        )
        dn_strength_row.addWidget(self.dn_value_label)
        dn_layout.addLayout(dn_strength_row)

        dn_info = QLabel("Reduces background hiss and surface noise")
        dn_info.setStyleSheet("color: #888; font-size: 10px;")
        dn_layout.addWidget(dn_info)

        layout.addWidget(dn_group)

        # Preview controls
        prev_group = QGroupBox("Preview")
        prev_layout = QHBoxLayout(prev_group)

        self.preview_btn = QPushButton("Play Before")
        self.preview_btn.setEnabled(False)

        self.preview_after_btn = QPushButton("Play After")
        self.preview_after_btn.setEnabled(False)

        prev_layout.addWidget(self.preview_btn)
        prev_layout.addWidget(self.preview_after_btn)
        prev_layout.addStretch()

        layout.addWidget(prev_group)

        # Process button
        process_row = QHBoxLayout()
        self.process_btn = QPushButton("Process Full Recording")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.process_requested.emit)
        self.process_btn.setStyleSheet(
            "QPushButton { background: #2a6b2a; padding: 8px 24px; font-weight: bold; } "
            "QPushButton:disabled { background: #333; }"
        )
        process_row.addStretch()
        process_row.addWidget(self.process_btn)
        process_row.addStretch()
        layout.addLayout(process_row)

        layout.addStretch()

    def get_settings(self) -> dict:
        """Return current restoration settings as a dict."""
        return {
            "highpass": {
                "enabled": self.hp_enable.isChecked(),
                "cutoff": self.hp_freq.value(),
            },
            "declick": {
                "enabled": self.dc_enable.isChecked(),
                "strength": self.dc_strength.value() / 100.0,
            },
            "denoise": {
                "enabled": self.dn_enable.isChecked(),
                "strength": self.dn_strength.value() / 100.0,
            },
            "preset": self.preset_combo.currentText(),
        }

    def _emit_settings(self):
        self.settings_changed.emit(self.get_settings())

    def _apply_preset(self, index: int):
        """Apply preset values to all controls."""
        presets = {
            0: {  # None
                "hp": (False, 30),
                "dc": (False, 0),
                "dn": (False, 0),
            },
            1: {  # Light
                "hp": (True, 30),
                "dc": (True, 25),
                "dn": (True, 15),
            },
            2: {  # Standard
                "hp": (True, 30),
                "dc": (True, 50),
                "dn": (True, 30),
            },
            3: {  # Aggressive
                "hp": (True, 40),
                "dc": (True, 80),
                "dn": (True, 60),
            },
        }
        preset = presets.get(index, presets[0])
        hp_en, hp_freq = preset["hp"]
        dc_en, dc_str = preset["dc"]
        dn_en, dn_str = preset["dn"]

        self.hp_enable.blockSignals(True)
        self.dc_enable.blockSignals(True)
        self.dn_enable.blockSignals(True)
        self.hp_freq.blockSignals(True)
        self.dc_strength.blockSignals(True)
        self.dn_strength.blockSignals(True)

        self.hp_enable.setChecked(hp_en)
        self.hp_freq.setValue(hp_freq)
        self.dc_enable.setChecked(dc_en)
        self.dc_strength.setValue(dc_str)
        self.dn_enable.setChecked(dn_en)
        self.dn_strength.setValue(dn_str)

        self.hp_enable.blockSignals(False)
        self.dc_enable.blockSignals(False)
        self.dn_enable.blockSignals(False)
        self.hp_freq.blockSignals(False)
        self.dc_strength.blockSignals(False)
        self.dn_strength.blockSignals(False)

        self._emit_settings()
