"""Split Tracks tab — waveform review, marker editing, and export controls."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from vinylripper.core.markers import (
    Marker,
    MarkerKind,
    create_pair,
    markers_from_ints,
    markers_to_ints,
    unlink_pair,
)
from vinylripper.core.states import RecordingState
from vinylripper.ui.waveform_widget import WaveformWidget


class SplitTracksTab(QWidget):
    """Waveform review, marker editing, and split/export controls."""

    split_export_requested = pyqtSignal()
    save_requested = pyqtSignal()
    markers_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Waveform
        self.waveform = WaveformWidget()
        self.waveform.markers_changed.connect(self._on_markers_changed)
        layout.addWidget(self.waveform, 1)

        # Marker tools
        tools_row = QHBoxLayout()
        tools_row.setSpacing(6)

        self.join_btn = QPushButton("Join Markers")
        self.join_btn.setEnabled(False)
        self.join_btn.clicked.connect(self._join_selected)
        tools_row.addWidget(self.join_btn)

        self.split_btn = QPushButton("Split Markers")
        self.split_btn.setEnabled(False)
        self.split_btn.clicked.connect(self._split_selected)
        tools_row.addWidget(self.split_btn)

        tools_row.addStretch()

        self.marker_info = QLabel("")
        self.marker_info.setStyleSheet("color: #888; font-size: 10px;")
        tools_row.addWidget(self.marker_info)

        layout.addLayout(tools_row)

        # Split controls
        split_row = QHBoxLayout()
        split_row.setSpacing(8)

        self.threshold_label = QLabel("Silence:")
        split_row.addWidget(self.threshold_label)
        less = QLabel("Fine")
        less.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(less)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(20, 60)
        self.threshold_slider.setValue(40)
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(5)
        split_row.addWidget(self.threshold_slider, 1)
        strict = QLabel("Strict")
        strict.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(strict)

        split_row.addSpacing(16)

        self.gap_label = QLabel("Min Gap:")
        split_row.addWidget(self.gap_label)
        short = QLabel("Short")
        short.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(short)
        self.gap_slider = QSlider(Qt.Orientation.Horizontal)
        self.gap_slider.setRange(100, 5000)
        self.gap_slider.setValue(1500)
        self.gap_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gap_slider.setTickInterval(500)
        split_row.addWidget(self.gap_slider, 1)
        long = QLabel("Long")
        long.setStyleSheet("color: #666; font-size: 10px;")
        split_row.addWidget(long)

        layout.addLayout(split_row)

        # Side gap controls
        side_gap_row = QHBoxLayout()
        side_gap_row.setSpacing(8)

        side_gap_row.addWidget(QLabel("Side gap:"))
        self.side_gap_mode = QLabel("keep")  # Will be replaced with QComboBox later
        self.side_gap_mode.setStyleSheet("color: #a0a0b0; font-size: 10px;")
        side_gap_row.addWidget(self.side_gap_mode)
        side_gap_row.addStretch()

        layout.addLayout(side_gap_row)

        # Export buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.save_btn = QPushButton("Save As...")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_requested.emit)
        btn_row.addWidget(self.save_btn)

        self.export_btn = QPushButton("Split & Export")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.split_export_requested.emit)
        btn_row.addWidget(self.export_btn)

        self.status_label = QLabel("Ready — record to preview splits")
        self.status_label.setStyleSheet("color: #666;")
        btn_row.addWidget(self.status_label, 1)

        layout.addLayout(btn_row)

    def set_session(self, session):
        self._session = session
        if session and session.markers:
            self._apply_markers()

    def set_full_audio(self, data: np.ndarray, samplerate: int):
        """Load recorded audio into waveform for review."""
        self.waveform.set_full_audio(data, samplerate)
        self.save_btn.setEnabled(data is not None and len(data) > 0)

    def set_split_markers(self, points: list[int]):
        """Update split markers on waveform."""
        markers = markers_from_ints(points)
        self._session.markers = markers if self._session else []
        self.waveform.set_split_markers(points)
        self._update_marker_info()

    def set_track_labels(self, labels: list[tuple[int, str]]):
        """Set track labels to overlay on waveform.

        Args:
            labels: List of (sample_position, label_text) tuples.
        """
        self.waveform.set_track_labels(labels)

    def get_split_points(self) -> list[int]:
        """Get current split positions as int list."""
        return self.waveform.get_split_markers()

    def _on_markers_changed(self, points: list[int]):
        """Handle marker changes from waveform widget."""
        if self._session:
            self._session.markers = markers_from_ints(points)
        self._update_marker_info()
        self.markers_updated.emit(points)

    def _update_marker_info(self):
        n = len(self.waveform.get_split_markers()) + 1
        self.marker_info.setText(f"{n} tracks")

    def _join_selected(self):
        """Join two adjacent markers into a locked pair."""
        points = self.waveform.get_split_markers()
        if len(points) < 2:
            return
        # Join the last two markers as a demonstration.
        # In a full implementation, user would select specific markers.
        p1 = points[-2]
        p2 = points[-1]
        m1 = Marker(position=p1)
        m2 = Marker(position=p2)
        create_pair(m1, m2, pair_id=hash((p1, p2)) % 10000)
        if self._session:
            session_markers = list(self._session.markers)
            # Update the relevant markers
            for i, m in enumerate(session_markers):
                if m.position == p1:
                    session_markers[i] = m1
                elif m.position == p2:
                    session_markers[i] = m2
            self._session.markers = session_markers
        self._update_marker_info()

    def _split_selected(self):
        """Break the last locked pair back into independent markers."""
        if not self._session:
            return
        markers = list(self._session.markers)
        for i, m in enumerate(markers):
            if m.kind == MarkerKind.LOCKED_PAIR and m.pair_id is not None:
                # Find its partner
                for j, m2 in enumerate(markers):
                    if i != j and m2.pair_id == m.pair_id:
                        unlink_pair(m, m2)
                        markers[i] = m
                        markers[j] = m2
                        break
        self._session.markers = markers
        self.waveform.set_split_markers(markers_to_ints(markers))
        self._update_marker_info()

    def update_state(self, state: RecordingState):
        """Update UI for recording state."""
        s = self._session
        markers = self.waveform.get_split_markers()
        has_markers = len(markers) > 0
        has_data = s is not None and s.recorded_data is not None

        self.export_btn.setEnabled(has_data and has_markers and state != RecordingState.PROCESSING)
        self.save_btn.setEnabled(has_data)

    def update_split_status(self, text: str):
        self.status_label.setText(text)
