"""Update notification dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox,
)

from core.version import VERSION
from core.updater import UpdateDownloader, apply_update_and_restart


class UpdateDialog(QDialog):
    """Shows update info and handles download + install."""

    def __init__(self, latest_version: str, release_notes: str,
                 download_url: str, parent=None):
        super().__init__(parent)
        self._download_url = download_url
        self._downloader: UpdateDownloader | None = None

        self.setWindowTitle("업데이트 알림")
        self.setFixedWidth(450)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title = QLabel("새 업데이트가 있습니다!")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        # Version info
        ver_label = QLabel(f"현재 버전: v{VERSION}  →  최신 버전: {latest_version}")
        ver_label.setStyleSheet("font-size: 13px; color: #a6adc8;")
        layout.addWidget(ver_label)

        # Release notes
        if release_notes:
            notes = QLabel(release_notes)
            notes.setWordWrap(True)
            notes.setStyleSheet(
                "font-size: 12px; color: #bac2de; background-color: #313244; "
                "padding: 10px; border-radius: 6px;"
            )
            notes.setMaximumHeight(150)
            layout.addWidget(notes)

        # Progress bar (hidden initially)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p% 다운로드 중...")
        self._progress.hide()
        layout.addWidget(self._progress)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 11px; color: #a6adc8;")
        self._status_label.hide()
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._later_btn = QPushButton("나중에")
        self._later_btn.setObjectName("cancel_btn")
        self._later_btn.setFixedHeight(32)
        self._later_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._later_btn)

        self._update_btn = QPushButton("지금 업데이트")
        self._update_btn.setObjectName("send_btn")
        self._update_btn.setFixedHeight(32)
        self._update_btn.setMinimumWidth(120)
        self._update_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self._update_btn)

        layout.addLayout(btn_row)

    def _start_download(self):
        self._update_btn.setEnabled(False)
        self._later_btn.setEnabled(False)
        self._update_btn.setText("다운로드 중...")
        self._progress.show()
        self._status_label.show()
        self._status_label.setText("다운로드를 시작합니다...")

        self._downloader = UpdateDownloader(self._download_url)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.download_finished.connect(self._on_download_finished)
        self._downloader.download_failed.connect(self._on_download_failed)
        self._downloader.start()

    def _on_progress(self, percent: int):
        self._progress.setValue(percent)
        self._status_label.setText(f"다운로드 중... {percent}%")

    def _on_download_finished(self, zip_path: str):
        self._status_label.setText("업데이트를 적용합니다. 앱이 재시작됩니다...")
        self._progress.setFormat("완료!")

        reply = QMessageBox.information(
            self, "업데이트 준비 완료",
            "다운로드가 완료되었습니다.\n"
            "확인을 누르면 앱이 종료되고 업데이트가 적용됩니다.",
            QMessageBox.StandardButton.Ok,
        )
        if reply == QMessageBox.StandardButton.Ok:
            apply_update_and_restart(zip_path)

    def _on_download_failed(self, error: str):
        self._update_btn.setEnabled(True)
        self._later_btn.setEnabled(True)
        self._update_btn.setText("다시 시도")
        self._progress.hide()
        self._status_label.setText(f"다운로드 실패: {error}")

    def closeEvent(self, event):
        if self._downloader and self._downloader.isRunning():
            event.ignore()
            return
        super().closeEvent(event)
