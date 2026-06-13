from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from vinylripper.core.config import get_config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 480)
        self.setModal(True)

        self._config = get_config()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout(output_group)
        output_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._output_dir = QComboBox()
        self._output_dir.setEditable(True)
        self._output_dir.addItem(self._config.default_output_dir)
        self._output_dir.setMinimumWidth(300)
        output_layout.addRow("Output Directory:", self._output_dir)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_output_dir)
        output_layout.addRow("", browse_btn)

        self._output_format = QComboBox()
        self._output_format.addItems(["flac", "mp3", "aiff"])
        output_layout.addRow("Output Format:", self._output_format)

        self._flac_compression = QSpinBox()
        self._flac_compression.setRange(0, 8)
        output_layout.addRow("FLAC Compression (0-8):", self._flac_compression)

        self._mp3_quality = QComboBox()
        self._mp3_quality.addItems(["0 (VBR ~245 kbps)", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
        output_layout.addRow("MP3 Quality (0-9):", self._mp3_quality)

        layout.addWidget(output_group)

        audio_group = QGroupBox("Audio Processing")
        audio_layout = QFormLayout(audio_group)
        audio_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._silence_threshold = QDoubleSpinBox()
        self._silence_threshold.setRange(-60, -10)
        self._silence_threshold.setSingleStep(1)
        self._silence_threshold.setSuffix(" dB")
        audio_layout.addRow("Silence Threshold:", self._silence_threshold)

        self._min_silence = QDoubleSpinBox()
        self._min_silence.setRange(0.1, 10.0)
        self._min_silence.setSingleStep(0.1)
        self._min_silence.setSuffix(" s")
        audio_layout.addRow("Min Silence Duration:", self._min_silence)

        self._min_track = QDoubleSpinBox()
        self._min_track.setRange(5, 300)
        self._min_track.setSingleStep(1)
        self._min_track.setSuffix(" s")
        audio_layout.addRow("Min Track Length:", self._min_track)

        self._restoration_level = QSpinBox()
        self._restoration_level.setRange(0, 2)
        self._restoration_level.setToolTip(
            "0 = None\n"
            "1 = Highpass filter (30 Hz rumble removal)\n"
            "2 = Highpass + Declick"
        )
        audio_layout.addRow("Restoration Level:", self._restoration_level)

        layout.addWidget(audio_group)

        discogs_group = QGroupBox("Discogs")
        discogs_layout = QFormLayout(discogs_group)
        discogs_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._discogs_token = QComboBox()
        self._discogs_token.setEditable(True)
        current_token = self._config.discogs_token
        if current_token:
            masked = "*" * (len(current_token) - 4) + current_token[-4:] if len(current_token) > 4 else "****"
            self._discogs_token.addItem(masked)
            self._discogs_token.setCurrentText(masked)
        discogs_layout.addRow("Personal Access Token:", self._discogs_token)

        token_hint = QLabel(
            '<a href="https://www.discogs.com/settings/developers" style="color:#0a8fcf;">Get token at discogs.com/settings/developers</a>'
        )
        token_hint.setOpenExternalLinks(True)
        token_hint.setWordWrap(True)
        discogs_layout.addRow("", token_hint)

        layout.addWidget(discogs_group)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _load_values(self):
        self._output_dir.setCurrentText(self._config.default_output_dir)
        self._output_format.setCurrentText(self._config.default_output_format)
        self._flac_compression.setValue(self._config.default_flac_compression)
        self._mp3_quality.setCurrentText(f"{self._config.default_mp3_quality} (VBR ~245 kbps)" if self._config.default_mp3_quality == "0" else self._config.default_mp3_quality)
        self._silence_threshold.setValue(self._config.silence_threshold_db)
        self._min_silence.setValue(self._config.min_silence_duration)
        self._min_track.setValue(self._config.min_track_length)
        self._restoration_level.setValue(self._config.default_restoration_level)

    def _browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self._config.default_output_dir
        )
        if dir_path:
            self._output_dir.setCurrentText(dir_path)

    def _save(self):
        output_dir = self._output_dir.currentText().strip()
        if not output_dir:
            QMessageBox.warning(self, "Invalid Path", "Please specify an output directory.")
            return

        self._config.set("default_output_dir", output_dir)
        self._config.set("default_output_format", self._output_format.currentText())
        self._config.set("default_flac_compression", self._flac_compression.value())

        mp3_quality_text = self._mp3_quality.currentText()
        if " " in mp3_quality_text:
            mp3_quality = mp3_quality_text.split(" ")[0]
        else:
            mp3_quality = mp3_quality_text
        self._config.set("default_mp3_quality", mp3_quality)

        self._config.set("silence_threshold_db", self._silence_threshold.value())
        self._config.set("min_silence_duration", self._min_silence.value())
        self._config.set("min_track_length", self._min_track.value())
        self._config.set("default_restoration_level", self._restoration_level.value())

        token_text = self._discogs_token.currentText().strip()
        if token_text and not token_text.startswith("*"):
            self._config.set("discogs_token", token_text)

        if self._config.save():
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to save settings.")

