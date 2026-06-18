import numpy as np
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygon,
)
from PyQt6.QtWidgets import QWidget

MAX_SAMPLES = 262144
MARKER_HIT_RADIUS = 8
MIN_MARKER_SEPARATION_SAMPLES = 22050
MAX_UNDO_STACK = 50


class WaveformWidget(QWidget):
    markers_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buf = np.zeros(MAX_SAMPLES, dtype=np.float32)
        self._write_pos = 0
        self._count = 0
        self._display_duration = 3.0
        self._samplerate = 44100
        self._recording = False
        self._peak = 1.0

        self._full_audio = None
        self._full_samplerate = 44100
        self._full_total_samples = 0
        self._split_markers = []
        self._dragging_index = -1
        self._hovered_index = -1

        # Undo/Redo stacks
        self._undo_stack = []
        self._redo_stack = []

        self.setMinimumHeight(150)
        self.setMouseTracking(True)

    def set_samplerate(self, sr):
        self._samplerate = sr

    def set_recording(self, active):
        self._recording = active
        if active:
            self._peak = 1.0

    def enqueue(self, samples):
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        n = len(samples)
        if n == 0:
            return
        end = self._write_pos + n
        if end <= MAX_SAMPLES:
            self._buf[self._write_pos : end] = samples
        else:
            first = MAX_SAMPLES - self._write_pos
            self._buf[self._write_pos :] = samples[:first]
            self._buf[: n - first] = samples[first:]
        self._write_pos = (self._write_pos + n) % MAX_SAMPLES
        self._count += n
        self.update()

    def reset(self):
        self._write_pos = 0
        self._count = 0
        self._peak = 1.0
        self._full_audio = None
        self._full_total_samples = 0
        self._split_markers = []
        self._dragging_index = -1
        self._hovered_index = -1
        self.update()

    def set_full_audio(self, data, samplerate):
        if data.ndim > 1:
            self._full_audio = data.mean(axis=1).astype(np.float32)
        else:
            self._full_audio = data.astype(np.float32)
        self._full_samplerate = samplerate
        self._full_total_samples = len(self._full_audio)
        self.update()

    def set_split_markers(self, points):
        self._split_markers = sorted(points)
        self.update()

    def get_split_markers(self):
        return sorted(self._split_markers)

    def clear_review(self):
        self._full_audio = None
        self._full_total_samples = 0
        self._split_markers = []
        self._dragging_index = -1
        self._hovered_index = -1
        self.update()

    def _sample_to_x(self, sample, margin, plot_w):
        if self._full_total_samples <= 0:
            return margin
        return margin + int(sample / self._full_total_samples * plot_w)

    def _x_to_sample(self, x, margin, plot_w):
        if plot_w <= 0:
            return 0
        frac = (x - margin) / plot_w
        return int(np.clip(frac, 0, 1) * self._full_total_samples)

    def _find_marker_at(self, x, margin, plot_w):
        closest = -1
        closest_dist = MARKER_HIT_RADIUS
        for i, sp in enumerate(self._split_markers):
            mx = self._sample_to_x(sp, margin, plot_w)
            dist = abs(x - mx)
            if dist < closest_dist:
                closest_dist = dist
                closest = i
        return closest

    def _draw_waveform_bands(
        self, painter, data, scale, mid, plot_h, x_offset, color_top, color_bottom
    ):
        n = len(data)
        plot_w = self.width() - 20
        spx = max(1, n // plot_w) if n > plot_w else 1
        usable = (n // spx) * spx
        if usable < spx:
            return

        chunks = data[:usable].reshape(-1, spx)
        mins = np.min(chunks, axis=1)
        maxs = np.max(chunks, axis=1)
        px_count = len(mins)

        half_h = plot_h / 2 - 4
        y_pos = mid - (mins / scale) * half_h
        y_neg = mid - (maxs / scale) * half_h
        tops = np.minimum(y_pos, y_neg).astype(int)
        bots = np.maximum(y_pos, y_neg).astype(int)

        grad = QLinearGradient(0, 10, 0, 10 + plot_h)
        grad.setColorAt(0.0, color_top)
        grad.setColorAt(1.0, color_bottom)
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(color_bottom, 1))

        for x in range(px_count):
            painter.drawLine(x + x_offset, tops[x], x + x_offset, bots[x])

        painter.setPen(QPen(QColor(45, 45, 55), 1))
        painter.drawLine(x_offset, int(mid), x_offset + plot_w, int(mid))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 10
        bottom_margin = 24
        plot_h = h - bottom_margin
        mid = margin + plot_h / 2

        painter.fillRect(self.rect(), QColor(18, 18, 24))

        if self._full_audio is not None and not self._recording:
            self._draw_full_review(painter, w, h, margin, plot_h, bottom_margin, mid)
        else:
            self._draw_live(painter, w, h, margin, plot_h, bottom_margin, mid)

        painter.end()

    def _draw_live(self, painter, w, h, margin, plot_h, bottom_margin, mid):
        count = self._count
        if count == 0:
            self._draw_live_time_axis(painter, w, h, margin, plot_h, bottom_margin, 0)
            return

        samples_to_show = min(count, int(self._display_duration * self._samplerate))
        start = (self._write_pos - samples_to_show) % MAX_SAMPLES

        if start + samples_to_show <= MAX_SAMPLES:
            data = self._buf[start : start + samples_to_show]
        else:
            first = MAX_SAMPLES - start
            rest = samples_to_show - first
            data = np.empty(samples_to_show, dtype=np.float32)
            data[:first] = self._buf[start:]
            data[first:] = self._buf[:rest]

        if len(data) < 2:
            self._draw_live_time_axis(painter, w, h, margin, plot_h, bottom_margin, 0)
            return

        current_peak = float(np.max(np.abs(data)))
        if current_peak > self._peak:
            self._peak = current_peak
        else:
            self._peak = self._peak * 0.995 + current_peak * 0.005

        scale = max(self._peak, 1e-10)

        self._draw_waveform_bands(
            painter,
            data,
            scale,
            mid,
            plot_h,
            0,
            QColor(0, 160, 220),
            QColor(0, 200, 255),
        )

        if self._recording:
            painter.setPen(QPen(QColor(255, 70, 70), 2))
            painter.drawLine(w - 1, margin, w - 1, margin + plot_h)
        total_time = samples_to_show / self._samplerate if self._samplerate > 0 else 0
        self._draw_live_time_axis(
            painter, w, h, margin, plot_h, bottom_margin, total_time
        )

    def _draw_full_review(self, painter, w, h, margin, plot_h, bottom_margin, mid):
        data = self._full_audio
        total = (
            self._full_total_samples / self._full_samplerate
            if self._full_samplerate > 0
            else 0
        )

        if data is None or len(data) < 2:
            self._draw_review_time_axis(
                painter, w, h, margin, plot_h, bottom_margin, total
            )
            return

        current_peak = float(np.max(np.abs(data)))
        scale = max(current_peak, 1e-10)

        plot_w = w - 2 * margin
        self._draw_waveform_bands(
            painter,
            data,
            scale,
            mid,
            plot_h,
            margin,
            QColor(0, 120, 180),
            QColor(0, 160, 220),
        )
        for i, sp in enumerate(self._split_markers):
            x = self._sample_to_x(sp, margin, plot_w)
            is_active = i == self._dragging_index or i == self._hovered_index
            color = QColor(255, 200, 50) if is_active else QColor(255, 160, 40)
            painter.setPen(QPen(color, 2))
            painter.drawLine(x, margin, x, margin + plot_h)

            if is_active:
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                poly = QPolygon(
                    [
                        QPoint(x, margin),
                        QPoint(x - 5, margin + 8),
                        QPoint(x + 5, margin + 8),
                    ]
                )
                painter.drawPolygon(poly)

        self._draw_review_time_axis(painter, w, h, margin, plot_h, bottom_margin, total)

    def _draw_live_time_axis(
        self, painter, w, h, margin, plot_h, bottom_margin, total_time
    ):
        painter.setFont(QFont("monospace", 8))
        fm = QFontMetrics(painter.font())
        interval = self._tick_interval(total_time)

        t = 0.0
        while t <= total_time + 0.001:
            frac = t / total_time if total_time > 0 else 0
            x = w - int(frac * w)
            label = f"{t:.0f}s"
            tw = fm.horizontalAdvance(label)
            painter.setPen(QPen(QColor(70, 70, 80), 1))
            painter.drawLine(x, margin + plot_h, x, margin + plot_h + 5)
            painter.setPen(QColor(130, 130, 140))
            painter.drawText(x - tw // 2, margin + plot_h + 16, label)
            t += interval

    def _draw_review_time_axis(
        self, painter, w, h, margin, plot_h, bottom_margin, total_time
    ):
        painter.setFont(QFont("monospace", 8))
        fm = QFontMetrics(painter.font())
        interval = self._tick_interval(total_time)
        plot_w = w - 2 * margin

        t = 0.0
        while t <= total_time + 0.001:
            frac = t / total_time if total_time > 0 else 0
            x = margin + int(frac * plot_w)
            label = f"{t:.0f}s"
            tw = fm.horizontalAdvance(label)
            painter.setPen(QPen(QColor(70, 70, 80), 1))
            painter.drawLine(x, margin + plot_h, x, margin + plot_h + 5)
            painter.setPen(QColor(130, 130, 140))
            painter.drawText(x - tw // 2, margin + plot_h + 16, label)
            t += interval

    @staticmethod
    def _tick_interval(total_time):
        if total_time <= 1:
            return 0.2
        elif total_time <= 5:
            return 1.0
        elif total_time <= 15:
            return 2.0
        elif total_time <= 30:
            return 5.0
        elif total_time <= 120:
            return 15.0
        elif total_time <= 600:
            return 30.0
        else:
            return 60.0

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        if self._full_audio is None or self._recording:
            super().mousePressEvent(event)
            return

        w = self.width()
        margin = 10
        plot_w = w - 2 * margin

        idx = self._find_marker_at(int(event.position().x()), margin, plot_w)
        if idx >= 0:
            self._dragging_index = idx
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        w = self.width()
        margin = 10
        plot_w = w - 2 * margin
        x = int(event.position().x())

        if self._dragging_index >= 0:
            new_sample = self._x_to_sample(x, margin, plot_w)
            markers = list(self._split_markers)

            lo = 0
            hi = self._full_total_samples
            if self._dragging_index > 0:
                lo = markers[self._dragging_index - 1] + MIN_MARKER_SEPARATION_SAMPLES
            if self._dragging_index < len(markers) - 1:
                hi = markers[self._dragging_index + 1] - MIN_MARKER_SEPARATION_SAMPLES

            markers[self._dragging_index] = int(np.clip(new_sample, lo, hi))
            self._split_markers = markers
            self.markers_changed.emit(list(self._split_markers))
            self.update()
            event.accept()
            return

        idx = self._find_marker_at(x, margin, plot_w)
        if idx >= 0:
            self._hovered_index = idx
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._hovered_index = -1
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging_index >= 0:
            self._dragging_index = -1
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hovered_index = -1
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def _push_undo(self):
        """Push current marker state to undo stack."""
        self._undo_stack.append(list(self._split_markers))
        if len(self._undo_stack) > MAX_UNDO_STACK:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self):
        """Undo last marker change."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(list(self._split_markers))
        self._split_markers = self._undo_stack.pop()
        self.markers_changed.emit(list(self._split_markers))
        self.update()
        return True

    def redo(self):
        """Redo last undone marker change."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(list(self._split_markers))
        self._split_markers = self._redo_stack.pop()
        self.markers_changed.emit(list(self._split_markers))
        self.update()
        return True

    def can_undo(self):
        return len(self._undo_stack) > 0

    def can_redo(self):
        return len(self._redo_stack) > 0

    def clear_undo_stack(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    def add_marker_at_sample(self, sample):
        """Add a new split marker at the given sample position."""
        markers = list(self._split_markers)
        insert_idx = 0
        for i, m in enumerate(markers):
            if sample < m:
                insert_idx = i
                break
            insert_idx = i + 1

        if (
            insert_idx > 0
            and sample - markers[insert_idx - 1] < MIN_MARKER_SEPARATION_SAMPLES
        ):
            return False
        if (
            insert_idx < len(markers)
            and markers[insert_idx] - sample < MIN_MARKER_SEPARATION_SAMPLES
        ):
            return False

        self._push_undo()
        markers.insert(insert_idx, sample)
        self._split_markers = markers
        self.markers_changed.emit(list(self._split_markers))
        self.update()
        return True

    def remove_marker_at_index(self, index):
        """Remove marker at the given index."""
        if 0 <= index < len(self._split_markers):
            self._push_undo()
            self._split_markers.pop(index)
            self.markers_changed.emit(list(self._split_markers))
            self.update()
            return True
        return False

    def draw_minimap(self, painter, rect: QRect):
        """Draw a minimap overview of the full waveform."""
        if self._full_audio is None or len(self._full_audio) < 2:
            return

        data = self._full_audio
        margin = 2
        w = rect.width() - 2 * margin
        h = rect.height() - 2 * margin
        if w <= 0 or h <= 0:
            return

        # Downsample for minimap
        spx = max(1, len(data) // w)
        usable = (len(data) // spx) * spx
        if usable < spx:
            return

        chunks = data[:usable].reshape(-1, spx)
        mins = np.min(chunks, axis=1)
        maxs = np.max(chunks, axis=1)
        px_count = len(mins)

        mid = rect.top() + margin + h / 2
        half_h = h / 2 - 1

        # Draw background
        painter.fillRect(rect, QColor(20, 20, 28))

        # Draw waveform
        painter.setPen(QPen(QColor(0, 120, 180), 1))
        for x in range(px_count):
            y1 = mid - (mins[x] * half_h)
            y2 = mid - (maxs[x] * half_h)
            painter.drawLine(
                rect.left() + margin + x, int(y1), rect.left() + margin + x, int(y2)
            )

        # Draw center line
        painter.setPen(QPen(QColor(45, 45, 55), 1))
        painter.drawLine(
            rect.left() + margin, int(mid), rect.right() - margin, int(mid)
        )

        # Draw split markers
        for _i, sp in enumerate(self._split_markers):
            x = rect.left() + margin + int(sp / self._full_total_samples * w)
            color = QColor(255, 160, 40)
            painter.setPen(QPen(color, 1))
            painter.drawLine(x, rect.top() + margin, x, rect.bottom() - margin)

        # Draw border
        painter.setPen(QPen(QColor(60, 60, 70), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
