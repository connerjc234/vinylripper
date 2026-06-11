from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QWidget,
    QLabel,
    QMessageBox,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

from vinylripper.core.config import load_config, save_config
from vinylripper.core.discogs_client import DiscogsClient, DiscogsSearchResult
from vinylripper.core.metadata import AlbumMetadata


class SearchThread(QThread):
    finished = pyqtSignal(list, object)
    error = pyqtSignal(str)

    def __init__(self, client, query, page=1):
        super().__init__()
        self.client = client
        self.query = query
        self.page = page

    def run(self):
        try:
            results, pagination = self.client.search(self.query, page=self.page)
            self.finished.emit(results, pagination)
        except Exception as e:
            self.error.emit(str(e))


class DetailThread(QThread):
    finished = pyqtSignal(AlbumMetadata)
    error = pyqtSignal(str)

    def __init__(self, client, result):
        super().__init__()
        self.client = client
        self.result = result

    def run(self):
        try:
            release_data = self.client.get_release(self.result.id)
            metadata = self._build_metadata(release_data)
            self.finished.emit(metadata)
        except Exception as e:
            self.error.emit(str(e))

    def _build_metadata(self, data: dict) -> AlbumMetadata:
        artists = [a.get("name", "") for a in data.get("artists", []) if a.get("name")]
        labels = [
            label.get("name", "")
            for label in data.get("labels", [])
            if label.get("name")
        ]
        catnos = [
            label.get("catno", "")
            for label in data.get("labels", [])
            if label.get("catno")
        ]

        cover_url = ""
        images = data.get("images", [])
        primary = [img for img in images if img.get("type") == "primary"]
        if primary:
            cover_url = primary[0].get("uri", "")
        elif images:
            cover_url = images[0].get("uri", "")
        if not cover_url:
            cover_url = self.result.cover_url

        cover_data = None
        cover_mime = "image/jpeg"
        if cover_url:
            cover_data, cover_mime = self.client.fetch_cover(cover_url)

        tracklist = []
        for t in data.get("tracklist", []):
            tracklist.append(
                {
                    "position": t.get("position", ""),
                    "title": t.get("title", ""),
                    "duration": t.get("duration", ""),
                }
            )

        return AlbumMetadata(
            artist=", ".join(artists) if artists else self.result.artist,
            title=data.get("title", self.result.release_title),
            year=data.get("year", self.result.year) or 0,
            label=", ".join(labels) if labels else self.result.label,
            catalog_number=", ".join(c for c in catnos if c),
            genres=data.get("genres", []),
            styles=data.get("styles", []),
            tracklist=tracklist,
            cover_data=cover_data,
            cover_mime=cover_mime,
            discogs_id=data.get("id", self.result.id),
        )


DIALOG_STYLE = """
QDialog {
    background-color: #1a1a20;
}
QLabel {
    background: transparent;
    color: #a0a0b0;
    font-size: 12px;
}
QLineEdit {
    background-color: #2a2a35;
    border: 1px solid #3a3a48;
    border-radius: 5px;
    padding: 6px 10px;
    color: #d0d0d8;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #0a8fcf;
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
QListWidget {
    background-color: #1e1e28;
    border: 1px solid #2a2a35;
    border-radius: 5px;
    outline: none;
}
QListWidget::item {
    border-bottom: 1px solid #252530;
}
QListWidget::item:selected {
    background-color: #0a3a5a;
}
"""


class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Discogs")
        self.setMinimumSize(680, 480)
        self.resize(760, 560)
        self.setStyleSheet(DIALOG_STYLE)

        self._client = None
        self._results = []
        self._metadata = None
        self._search_thread = None
        self._detail_thread = None

        self._build_ui()
        self._load_token()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title_label = QLabel("<h3 style='color:#e0e0e8; margin:0;'>Search Discogs</h3>")
        layout.addWidget(title_label)

        self._token_layout = QHBoxLayout()
        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText("Discogs Personal Access Token")
        self._token_layout.addWidget(self._token_input, 1)
        self._save_token_btn = QPushButton("Save Token")
        self._save_token_btn.clicked.connect(self._save_token)
        self._token_layout.addWidget(self._save_token_btn)
        layout.addLayout(self._token_layout)

        self._hint = QLabel(
            '<a href="https://www.discogs.com/settings/developers" '
            'style="color:#0a8fcf;">Get your token here</a>'
        )
        self._hint.setOpenExternalLinks(True)
        layout.addWidget(self._hint)

        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            "Search for artist, album, or catalog number…"
        )
        self._search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_input, 1)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        result_header = QLabel("Results:")
        layout.addWidget(result_header)

        self._results_list = QListWidget()
        self._results_list.setSpacing(0)
        self._results_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._results_list.itemDoubleClicked.connect(self._select_current)
        layout.addWidget(self._results_list, 1)

        btn_row = QHBoxLayout()
        self._select_btn = QPushButton("Select Result")
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(self._select_current)
        btn_row.addWidget(self._select_btn)

        self._skip_btn = QPushButton("Skip — Not on Discogs")
        self._skip_btn.clicked.connect(self._skip)
        btn_row.addWidget(self._skip_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        layout.addLayout(btn_row)

    def _load_token(self):
        cfg = load_config()
        token = cfg.get("discogs_token", "")
        if token:
            self._token_input.setText(token)
            self._init_client(token)
            self._token_input.setVisible(False)
            self._save_token_btn.setVisible(False)
            self._hint.setVisible(False)

    def _save_token(self):
        token = self._token_input.text().strip()
        if not token:
            QMessageBox.warning(
                self, "Token Required", "Please enter a valid Discogs token."
            )
            return
        save_config({"discogs_token": token})
        self._init_client(token)
        self._token_input.setVisible(False)
        self._save_token_btn.setVisible(False)

    def _init_client(self, token):
        self._client = DiscogsClient(token)

    def _do_search(self):
        if not self._client:
            QMessageBox.warning(
                self,
                "Token Required",
                "Please enter and save your Discogs Personal Access Token first.",
            )
            return
        query = self._search_input.text().strip()
        if not query:
            return
        self._search_btn.setEnabled(False)
        self._search_btn.setText("Searching…")
        self._select_btn.setEnabled(False)
        self._results_list.clear()
        self._results = []

        self._search_thread = SearchThread(self._client, query)
        self._search_thread.finished.connect(self._on_search_results)
        self._search_thread.error.connect(self._on_search_error)
        self._search_thread.start()

    def _on_search_results(self, results, pagination):
        self._results = results
        self._search_btn.setEnabled(True)
        self._search_btn.setText("Search")
        self._populate_results()
        self._search_thread = None

    def _on_search_error(self, msg):
        self._search_btn.setEnabled(True)
        self._search_btn.setText("Search")
        QMessageBox.critical(self, "Search Error", msg)
        self._search_thread = None

    def _populate_results(self):
        self._results_list.clear()
        for result in self._results:
            item = QListWidgetItem()
            widget = self._make_result_widget(result)
            item.setSizeHint(widget.sizeHint())
            self._results_list.addItem(item)
            self._results_list.setItemWidget(item, widget)
        if self._results:
            self._results_list.setCurrentRow(0)
            self._select_btn.setEnabled(True)

    def _make_result_widget(self, result: DiscogsSearchResult) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        thumb = QLabel()
        thumb.setFixedSize(48, 48)
        thumb.setStyleSheet(
            "background-color: #252530; border: 1px solid #333; border-radius: 3px;"
        )
        if result.thumb_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(result.thumb_data):
                thumb.setPixmap(
                    pixmap.scaled(
                        48,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        layout.addWidget(thumb)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_label = QLabel(
            f"<b style='color:#e0e0e8;'>{result.artist}</b>"
            f"<span style='color:#c0c0c8;'> — {result.release_title}</span>"
        )
        text_layout.addWidget(title_label)

        parts = []
        if result.year:
            parts.append(str(result.year))
        if result.label:
            parts.append(result.label)
        if result.catno:
            parts.append(result.catno)
        detail = QLabel("  |  ".join(parts) if parts else "")
        detail.setStyleSheet("color: #888; font-size: 10px;")
        text_layout.addWidget(detail)

        layout.addLayout(text_layout, 1)
        return widget

    def _select_current(self):
        item = self._results_list.currentItem()
        if item is None:
            return
        row = self._results_list.row(item)
        if row < 0 or row >= len(self._results):
            return
        result = self._results[row]

        self._select_btn.setEnabled(False)
        self._select_btn.setText("Fetching details…")
        self._skip_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)

        self._detail_thread = DetailThread(self._client, result)
        self._detail_thread.finished.connect(self._on_detail_ready)
        self._detail_thread.error.connect(self._on_detail_error)
        self._detail_thread.start()

    def _on_detail_ready(self, metadata):
        self._metadata = metadata
        self._detail_thread = None
        self.accept()

    def _on_detail_error(self, msg):
        self._select_btn.setEnabled(True)
        self._select_btn.setText("Select Result")
        self._skip_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to fetch release details:\n{msg}")
        self._detail_thread = None

    def _skip(self):
        self._metadata = AlbumMetadata()
        self.accept()

    @property
    def album_metadata(self) -> AlbumMetadata | None:
        return self._metadata
