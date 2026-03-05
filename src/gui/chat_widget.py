"""Chat display widget: message bubbles with bookmark support."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QFrame, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class MessageBubble(QFrame):
    """Single chat message bubble."""

    bookmark_requested = pyqtSignal(str)  # text to bookmark

    def __init__(self, role: str, text: str = "", parent=None):
        super().__init__(parent)
        self._role = role
        self.setObjectName(f"bubble_{role}")
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        role_label = QLabel("You" if role == "user" else "4Bro")
        role_label.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #89b4fa;"
            if role == "assistant"
            else "font-weight: bold; font-size: 12px; color: #a6e3a1;"
        )
        layout.addWidget(role_label)

        self._content = QLabel(text)
        self._content.setWordWrap(True)
        self._content.setTextFormat(Qt.TextFormat.PlainText)
        self._content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._content.setStyleSheet("color: #cdd6f4; font-size: 13px; padding: 4px 0;")
        layout.addWidget(self._content)

        # Right-click context menu for assistant messages
        if role == "assistant":
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        bookmark_action = menu.addAction("북마크 추가")
        copy_action = menu.addAction("전체 복사")
        save_action = menu.addAction("Word로 저장")

        action = menu.exec(self.mapToGlobal(pos))
        if action == bookmark_action:
            self.bookmark_requested.emit(self._content.text())
        elif action == copy_action:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._content.text())
        elif action == save_action:
            self._save_as_word()

    def _save_as_word(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Word로 저장", "", "Word Files (*.docx)")
        if path:
            try:
                from core.document_io import save_to_word
                save_to_word(self._content.text(), path)
            except Exception:
                pass

    def append_text(self, text: str):
        self._content.setText(self._content.text() + text)

    def set_text(self, text: str):
        self._content.setText(text)

    def get_text(self) -> str:
        return self._content.text()


class ChatWidget(QScrollArea):
    """Scrollable chat area containing message bubbles."""

    bookmark_requested = pyqtSignal(str)  # bubble text to bookmark

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setObjectName("chat_area")

        self._container = QWidget()
        self._container.setObjectName("chat_container")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)
        self._layout.addStretch()

        self.setWidget(self._container)

        self._bubbles: list[MessageBubble] = []
        self._streaming_bubble: MessageBubble | None = None

    def add_message(self, role: str, text: str) -> MessageBubble:
        bubble = MessageBubble(role, text)
        bubble.bookmark_requested.connect(self.bookmark_requested.emit)
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def start_streaming(self) -> MessageBubble:
        bubble = MessageBubble("assistant", "")
        bubble.bookmark_requested.connect(self.bookmark_requested.emit)
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        self._streaming_bubble = bubble
        return bubble

    def append_stream_token(self, token: str):
        if self._streaming_bubble:
            self._streaming_bubble.append_text(token)
            self._scroll_to_bottom()

    def finish_streaming(self) -> str:
        text = ""
        if self._streaming_bubble:
            text = self._streaming_bubble.get_text()
            self._streaming_bubble = None
        return text

    def clear_chat(self):
        for bubble in self._bubbles:
            self._layout.removeWidget(bubble)
            bubble.deleteLater()
        self._bubbles.clear()
        self._streaming_bubble = None

    def add_step_header(self, step_name: str, step_index: int, total: int):
        """Add a visual step header for agent mode."""
        header = QLabel(f"Step {step_index + 1}/{total}: {step_name}")
        header.setStyleSheet(
            "color: #f9e2af; font-weight: bold; font-size: 13px; "
            "padding: 8px 12px; background-color: #313244; border-radius: 6px;"
        )
        self._layout.insertWidget(self._layout.count() - 1, header)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(10, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))
