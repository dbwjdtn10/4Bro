"""Bottom input bar: text input, file/image attach, image gen, send button."""

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

    # Signal emitted when user requests image generation with current prompt
    image_gen_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc_texts: list[tuple[str, str]] = []  # [(filename, text), ...]
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
        self._attach_btn.setToolTip("파일 첨부 (PDF, Word, Excel, PPT, CSV, 텍스트)")
        self._attach_btn.clicked.connect(self._on_attach_file)
        input_row.addWidget(self._attach_btn)

        # Image attach button
        self._image_btn = QPushButton("🖼")
        self._image_btn.setObjectName("attach_btn")
        self._image_btn.setFixedSize(36, 36)
        self._image_btn.setToolTip("이미지 첨부 (분석용)")
        self._image_btn.clicked.connect(self._on_attach_image)
        input_row.addWidget(self._image_btn)

        # Image generation button
        self._image_gen_btn = QPushButton("🎨")
        self._image_gen_btn.setObjectName("attach_btn")
        self._image_gen_btn.setFixedSize(36, 36)
        self._image_gen_btn.setToolTip("이미지 생성 (입력 텍스트를 프롬프트로 사용)")
        self._image_gen_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #313244; color: #cba6f7; border: 1px solid #45475a;"
            "  border-radius: 6px; font-size: 16px;"
            "}"
            "QPushButton:hover { background-color: #45475a; border-color: #cba6f7; }"
            "QPushButton:disabled { color: #585b70; }"
        )
        self._image_gen_btn.clicked.connect(self._on_image_gen)
        input_row.addWidget(self._image_gen_btn)

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
        paths, _ = QFileDialog.getOpenFileNames(
            self, "파일 첨부 (여러 파일 선택 가능)", "",
            "Documents (*.pdf *.docx *.xlsx *.pptx *.csv *.txt *.md *.json *.xml *.html *.yaml *.yml *.log);;All Files (*)",
        )
        if not paths:
            return
        from core.document_io import read_document
        errors = []
        for path in paths:
            try:
                text = read_document(path)
                filename = os.path.basename(path)
                self._doc_texts.append((filename, text))
            except ValueError as e:
                if str(e) == "NO_TEXT" and path.lower().endswith(".pdf"):
                    self._attach_scanned_pdf(path)
                else:
                    errors.append(os.path.basename(path))
            except Exception:
                errors.append(os.path.basename(path))
        self._update_attach_label()
        if errors:
            self._attach_label.setText(
                self._attach_label.text() + f"  ⚠ 실패: {', '.join(errors)}"
            )

    def _update_attach_label(self):
        """Update the attachment label to reflect all attached docs."""
        if not self._doc_texts:
            self._attach_label.hide()
            self._attach_label.setText("")
            return
        if len(self._doc_texts) == 1:
            fname, text = self._doc_texts[0]
            self._attach_label.setText(f"📎 {fname} ({len(text):,}자)  [x]")
        else:
            total = sum(len(t) for _, t in self._doc_texts)
            names = [f for f, _ in self._doc_texts]
            self._attach_label.setText(
                f"📎 {len(names)}개 파일 ({', '.join(names)}) · 총 {total:,}자  [x]"
            )
        self._attach_label.show()
        self._attach_label.mousePressEvent = lambda e: self._clear_doc()

    def _attach_scanned_pdf(self, path: str):
        """Handle scanned/image PDF by rendering pages as images."""
        try:
            from core.document_io import render_pdf_as_images
            image_paths = render_pdf_as_images(path)
            if not image_paths:
                self._attach_label.setText("PDF에서 페이지를 읽을 수 없습니다.")
                self._attach_label.show()
                return

            self._image_paths.extend(image_paths)
            filename = os.path.basename(path)
            n_pages = len(image_paths)
            scan_text = f"이 PDF는 스캔된 이미지 문서입니다. 첨부된 {n_pages}장의 이미지를 분석해서 내용을 파악해 주세요."
            self._doc_texts.append((filename, scan_text))

            self._attach_label.setText(
                f"📎 {filename} (스캔 PDF → 이미지 {n_pages}장 변환)  [x]"
            )
            self._attach_label.show()
            # Clicking [x] clears both doc and images (they're linked for scanned PDFs)
            self._attach_label.mousePressEvent = lambda e: self._clear_all_attachments()

            # Also show in image label
            self._image_label.setText(
                f"🖼 PDF 페이지 이미지 {n_pages}장  [x]"
            )
            self._image_label.show()
            self._image_label.mousePressEvent = lambda e: self._clear_all_attachments()
        except Exception as e:
            self._attach_label.setText(f"PDF 이미지 변환 실패: {e}")
            self._attach_label.show()

    def _clear_all_attachments(self):
        """Clear both doc and images (used for scanned PDF where they're linked)."""
        self._clear_doc()
        self._clear_images()

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
        self._doc_texts = []
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
        # Combine all attached doc texts with file separators
        if len(self._doc_texts) == 1:
            combined = self._doc_texts[0][1]
        elif self._doc_texts:
            parts = []
            for fname, doc in self._doc_texts:
                parts.append(f"=== 📎 {fname} ===\n{doc}")
            combined = "\n\n".join(parts)
        else:
            combined = ""
        self.message_sent.emit(text, combined, list(self._image_paths))
        self._input.clear()
        self._clear_doc()
        self._clear_images()

    def _on_image_gen(self):
        """Emit image generation request with the current input text as prompt."""
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.image_gen_requested.emit(text)

    def set_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._attach_btn.setEnabled(enabled)
        self._image_btn.setEnabled(enabled)
        self._image_gen_btn.setEnabled(enabled)
        if enabled:
            self._send_btn.setText("전송")
        else:
            self._send_btn.setText("생성중...")

    def set_focus(self):
        self._input.setFocus()
