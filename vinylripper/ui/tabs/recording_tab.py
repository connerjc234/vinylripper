"""Recording Options tab — recording controls, side config, metadata display."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vinylripper.core.states import RecordingState


class RecordingTab(QWidget):
    """Recording controls, side configuration, and needle-down status."""

    record_toggled = pyqtSignal()
    sides_changed = pyqtSignal(int)
    discogs_search_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Top: Recording controls group
        ctrl_group = QGroupBox("Recording")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.setSpacing(8)

        # Record button + status
        record_row = QHBoxLayout()
        self.record_btn = QPushButton("Record")
        self.record_btn.setFixedHeight(36)
        self.record_btn.setMinimumWidth(140)
        self.record_btn.clicked.connect(self.record_toggled.emit)
        record_row.addWidget(self.record_btn)

        self.rec_status = QLabel("Ready")
        self.rec_status.setStyleSheet("color: #888; font-size: 12px;")
        record_row.addWidget(self.rec_status, 1)
        ctrl_layout.addLayout(record_row)

        # Metadata display + Discogs search
        meta_row = QHBoxLayout()
        self.metadata_label = QLabel("No album selected")
        self.metadata_label.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        self.metadata_label.setWordWrap(True)
        meta_row.addWidget(self.metadata_label, 1)
        self.discogs_btn = QPushButton("Search Discogs")
        self.discogs_btn.setFixedHeight(28)
        self.discogs_btn.clicked.connect(self.discogs_search_requested.emit)
        meta_row.addWidget(self.discogs_btn)
        ctrl_layout.addLayout(meta_row)

        # Track preview
        self.track_preview_group = QGroupBox("Tracks")
        track_preview_layout = QVBoxLayout(self.track_preview_group)
        track_preview_layout.setContentsMargins(8, 8, 8, 8)
        self.track_list = QListWidget()
        self.track_list.setMaximumHeight(200)
        self.track_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e28;
                border: 1px solid #2a2a35;
                border-radius: 4px;
                font-size: 11px;
            }
            QListWidget::item {
                color: #c0c0c8;
                padding: 2px 6px;
            }
        """)
        track_preview_layout.addWidget(self.track_list)
        self.track_preview_group.setVisible(False)
        ctrl_layout.addWidget(self.track_preview_group)

        layout.addWidget(ctrl_group)

        # Side configuration group
        side_group = QGroupBox("Side Configuration")
        side_layout = QVBoxLayout(side_group)
        side_layout.setSpacing(8)

        side_count_row = QHBoxLayout()
        side_count_row.addWidget(QLabel("Number of sides:"))
        self.sides_spin = QSpinBox()
        self.sides_spin.setRange(1, 4)
        self.sides_spin.setValue(2)
        self.sides_spin.valueChanged.connect(self.sides_changed.emit)
        side_count_row.addWidget(self.sides_spin)
        side_count_row.addStretch()
        side_layout.addLayout(side_count_row)

        side_status_row = QHBoxLayout()
        self.side_indicator = QLabel("Current Side: —")
        self.side_indicator.setStyleSheet("color: #888; font-size: 12px; font-weight: bold;")
        side_status_row.addWidget(self.side_indicator)
        self.side_progress = QLabel("")
        self.side_progress.setStyleSheet("color: #666; font-size: 10px;")
        side_status_row.addWidget(self.side_progress)
        side_status_row.addStretch()
        side_layout.addLayout(side_status_row)

        layout.addWidget(side_group)

        # Needle-down status group
        nd_group = QGroupBox("Needle-Down Detection")
        nd_layout = QVBoxLayout(nd_group)
        nd_layout.setSpacing(4)

        self.nd_status = QLabel("Calibration required")
        self.nd_status.setStyleSheet("color: #ff8800; font-size: 11px;")
        nd_layout.addWidget(self.nd_status)

        self.nd_noise_floor = QLabel("Noise floor: — dBFS")
        self.nd_noise_floor.setStyleSheet("color: #888; font-size: 10px;")
        nd_layout.addWidget(self.nd_noise_floor)

        layout.addWidget(nd_group)

        # Countdown timer display
        self.countdown_label = QLabel("")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(
            "color: #f5a623; font-size: 28px; font-weight: bold;"
        )
        self.countdown_label.setVisible(False)
        layout.addWidget(self.countdown_label)

        layout.addStretch()

    def set_session(self, session):
        """Connect this tab to the shared RecordingSession."""
        self._session = session
        if session:
            self.sides_spin.setValue(session.total_sides)
            self._update_side_display()
            self._update_nd_status()

    def _update_side_display(self):
        if not self._session:
            return
        s = self._session
        if s.state in (RecordingState.RECORDING, RecordingState.PAUSED,
                       RecordingState.FLIP_COUNTDOWN, RecordingState.STOPPED):
            self.side_indicator.setText(f"Current Side: {s.side_letter()} ({s.current_side}/{s.total_sides})")
            self.side_progress.setText("Recording" if s.state == RecordingState.RECORDING else "Complete" if s.state == RecordingState.STOPPED else "Paused")
        else:
            self.side_indicator.setText("Current Side: —")
            self.side_progress.setText("")

    def _update_nd_status(self):
        if not self._session:
            return
        s = self._session
        if s.calibrated:
            self.nd_status.setText("Needle-Down Detection: Ready ✅")
            self.nd_status.setStyleSheet("color: #4caf50; font-size: 11px;")
            self.nd_noise_floor.setText(f"Noise floor: {s.noise_floor_rms:.6f}")
        else:
            self.nd_status.setText("Calibration required — go to Check Level tab")
            self.nd_status.setStyleSheet("color: #ff8800; font-size: 11px;")

    def update_state(self, state: RecordingState):
        """Update UI to reflect current recording state."""
        s = self._session
        if state == RecordingState.IDLE:
            self.record_btn.setText("Record")
            self.record_btn.setEnabled(True)
            self.rec_status.setText("Ready")
            self.countdown_label.setVisible(False)
            self.sides_spin.setEnabled(True)
        elif state == RecordingState.RECORDING:
            self.record_btn.setText("Stop")
            self.record_btn.setEnabled(True)
            self.rec_status.setText(f"Recording Side {s.side_letter() if s else 'A'}...")
            self.rec_status.setStyleSheet("color: #ff4444; font-size: 12px; font-weight: bold;")
            self.countdown_label.setVisible(False)
            self.sides_spin.setEnabled(False)
        elif state == RecordingState.PAUSED:
            self.record_btn.setText("Stop")
            self.rec_status.setText(f"Paused — Side {s.side_letter() if s else ''} complete")
            self.rec_status.setStyleSheet("color: #ffaa00; font-size: 12px;")
        elif state == RecordingState.FLIP_COUNTDOWN:
            self.rec_status.setText("Flip the record...")
            self.rec_status.setStyleSheet("color: #f5a623; font-size: 12px; font-weight: bold;")
        elif state == RecordingState.STOPPED:
            self.record_btn.setText("Record")
            self.record_btn.setEnabled(True)
            self.rec_status.setText("Recording complete")
            self.rec_status.setStyleSheet("color: #4caf50; font-size: 12px;")
            self.sides_spin.setEnabled(True)
        elif state == RecordingState.PROCESSING:
            self.record_btn.setEnabled(False)

        self._update_side_display()

    def show_countdown(self, seconds: int):
        """Display countdown timer for record flip."""
        self.countdown_label.setVisible(True)
        self.countdown_label.setText(f"Flip record — {seconds}s")

    def hide_countdown(self):
        self.countdown_label.setVisible(False)

    def set_metadata_display(self, artist: str, title: str):
        """Update metadata label with album info."""
        if artist and title:
            self.metadata_label.setText(f"{artist} — {title}")
        elif artist:
            self.metadata_label.setText(artist)
        elif title:
            self.metadata_label.setText(title)
        else:
            self.metadata_label.setText("No album selected")

    def set_tracklist(
        self,
        tracklist: list[dict],
        side_tracklist: dict[str, list[dict]] | None = None,
    ):
        """Populate track preview list from Discogs metadata.

        Args:
            tracklist: Flat list of track dicts with 'position', 'title', 'duration'.
            side_tracklist: Optional dict grouping tracks by side letter.
        """
        self.track_list.clear()
        if not tracklist:
            self.track_preview_group.setVisible(False)
            return

        self.track_preview_group.setVisible(True)

        if side_tracklist:
            # Display grouped by side
            for side in sorted(side_tracklist, key=lambda s: (len(s), s)):
                # Side header
                header_item = QListWidgetItem(f"── Side {side} ──")
                header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                header_item.setForeground(QColor("#f5a623"))
                self.track_list.addItem(header_item)

                for t in side_tracklist[side]:
                    pos = t.get("position", "")
                    title = t.get("title", "")
                    dur = t.get("duration", "")
                    dur_str = f"  [{dur}]" if dur else ""
                    item = QListWidgetItem(f"  {pos}  {title}{dur_str}")
                    self.track_list.addItem(item)
        else:
            # Flat display
            for t in tracklist:
                pos = t.get("position", "")
                title = t.get("title", "")
                dur = t.get("duration", "")
                dur_str = f"  [{dur}]" if dur else ""
                item = QListWidgetItem(f"{pos}  {title}{dur_str}")
                self.track_list.addItem(item)

    def clear_countdown(self):
        self.countdown_label.setVisible(False)
