"""Bottom input bar: text input, file/image attach, send button."""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTextEdit, QPushButton,
    QLabel, QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent


class ChatInput(QTextEdit):
    """Text input that sends on Enter (Shift+Enter for newline)."""

    send_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("메시지를 입력하세요...")
        self.setMaximumHeight(100)
        self.setMinimumHeight(40)
        self.setObjectName("chat_input")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
        else:
            super().keyPressEvent(event)


class InputBar(QWidget):
    """Bottom bar with text input, attachments, and send button."""

    # (text, doc_text, list_of_image_paths)
    message_sent = pyqtSignal(str, str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc_text = ""
        self._doc_filename = ""
        self._image_paths: list[str] = []
        self.setObjectName("input_bar")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 12)
        layout.setSpacing(4)

        # Attachment indicators
        self._attach_label = QLabel("")
        self._attach_label.setObjectName("attach_label")
        self._attach_label.setStyleSheet("color: #89b4fa; font-size: 11px;")
        self._attach_label.hide()
        layout.addWidget(self._attach_label)

        # Image preview row
        self._image_label = QLabel("")
        self._image_label.setStyleSheet("color: #f9e2af; font-size: 11px;")
        self._image_label.hide()
        layout.addWidget(self._image_label)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        # File attach button
        self._attach_btn = QPushButton("📎")
        self._attach_btn.setObjectName("attach_btn")
        self._attach_btn.setFixedSize(36, 36)
        self._attach_btn.setToolTip("파일 첨부 (PDF, Word, txt)")
        self._attach_btn.clicked.connect(self._on_attach_file)
        input_row.addWidget(self._attach_btn)

        # Image attach button
        self._image_btn = QPushButton("🖼")
        self._image_btn.setObjectName("attach_btn")
        self._image_btn.setFixedSize(36, 36)
        self._image_btn.setToolTip("이미지 첨부 (분석용)")
        self._image_btn.clicked.connect(self._on_attach_image)
        input_row.addWidget(self._image_btn)

        # Text input
        self._input = ChatInput()
        input_row.addWidget(self._input, 1)

        # Send button
        self._send_btn = QPushButton("전송")
        self._send_btn.setObjectName("send_btn")
        self._send_btn.setFixedHeight(36)
        self._send_btn.setMinimumWidth(60)
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        self._input.send_requested.connect(self._on_send)

        layout.addLayout(input_row)

    def _on_attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "파일 첨부", "",
            "Documents (*.pdf *.docx *.doc *.txt);;All Files (*)",
        )
        if path:
            try:
                from core.document_io import read_document
                self._doc_text = read_document(path)
                self._doc_filename = os.path.basename(path)
                self._attach_label.setText(
                    f"📎 {self._doc_filename} ({len(self._doc_text):,}자)  [x]"
                )
                self._attach_label.show()
                self._attach_label.mousePressEvent = lambda e: self._clear_doc()
            except Exception as e:
                self._attach_label.setText(f"파일 읽기 실패: {e}")
                self._attach_label.show()
                self._doc_text = ""

    def _on_attach_image(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "이미지 첨부", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)",
        )
        if paths:
            self._image_paths.extend(paths)
            names = [os.path.basename(p) for p in self._image_paths]
            self._image_label.setText(
                f"🖼 {', '.join(names)}  [x]"
            )
            self._image_label.show()
            self._image_label.mousePressEvent = lambda e: self._clear_images()

    def _clear_doc(self):
        self._doc_text = ""
        self._doc_filename = ""
        self._attach_label.hide()
        self._attach_label.setText("")

    def _clear_images(self):
        self._image_paths = []
        self._image_label.hide()
        self._image_label.setText("")

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.message_sent.emit(text, self._doc_text, list(self._image_paths))
        self._input.clear()
        self._clear_doc()
        self._clear_images()

    def set_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._attach_btn.setEnabled(enabled)
        self._image_btn.setEnabled(enabled)
        if enabled:
            self._send_btn.setText("전송")
        else:
            self._send_btn.setText("생성중...")

    def set_focus(self):
        self._input.setFocus()
