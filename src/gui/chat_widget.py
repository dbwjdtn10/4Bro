"""Chat display widget: message bubbles with markdown rendering and bookmark support."""

from __future__ import annotations

import re
from html import escape

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QFrame, QMenu, QInputDialog,
    QTextBrowser,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


# ---------------------------------------------------------------------------
# Markdown -> HTML converter (regex-based, no external dependencies)
# ---------------------------------------------------------------------------

def markdown_to_html(text: str) -> str:
    """Convert a markdown string to styled HTML for display in QTextBrowser.

    Processing order matters: code blocks are extracted first so their
    contents are protected from subsequent transformations.
    """

    # --- Step 1: Extract fenced code blocks and protect them ---------------
    code_blocks: list[str] = []

    def _replace_code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = escape(m.group(2))
        block_html = (
            f'<pre style="background:#313244; padding:8px; border-radius:6px; '
            f'font-family:Consolas,monospace; font-size:13px; color:#cdd6f4; '
            f'overflow-x:auto; white-space:pre-wrap;">{code}</pre>'
        )
        placeholder = f"\x00CODEBLOCK{len(code_blocks)}\x00"
        code_blocks.append(block_html)
        return placeholder

    text = re.sub(
        r"```(\w*)\n(.*?)```",
        _replace_code_block,
        text,
        flags=re.DOTALL,
    )

    # --- Step 2: Inline code (before escaping the rest) --------------------
    inline_codes: list[str] = []

    def _replace_inline_code(m: re.Match) -> str:
        code = escape(m.group(1))
        inline_html = (
            f'<code style="background:#313244; padding:2px 5px; border-radius:3px; '
            f'font-family:Consolas,monospace; color:#f38ba8;">{code}</code>'
        )
        placeholder = f"\x00INLINECODE{len(inline_codes)}\x00"
        inline_codes.append(inline_html)
        return placeholder

    text = re.sub(r"`([^`\n]+)`", _replace_inline_code, text)

    # --- Step 3: Escape remaining HTML entities ----------------------------
    text = escape(text)

    # --- Step 4: Bold & Italic (bold first so **x** isn't caught by *x*) ---
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

    # --- Step 5: Headers (process line-by-line) ----------------------------
    _header_map = {
        "### ": ('<h4 style="color:#cba6f7; margin:8px 0 4px; font-size:14px;">', "</h4>"),
        "## ":  ('<h3 style="color:#cba6f7; margin:10px 0 4px; font-size:15px;">', "</h3>"),
        "# ":   ('<h2 style="color:#cba6f7; margin:12px 0 6px; font-size:16px;">', "</h2>"),
    }

    lines = text.split("\n")
    processed: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # --- Headers -------------------------------------------------------
        header_matched = False
        for prefix, (open_tag, close_tag) in _header_map.items():
            esc_prefix = escape(prefix)
            if stripped.startswith(esc_prefix):
                content = stripped[len(esc_prefix):]
                processed.append(f"{open_tag}{content}{close_tag}")
                header_matched = True
                break
        if header_matched:
            i += 1
            continue

        # --- Unordered list (- item or * item) -----------------------------
        if re.match(r"^[-*]\s+", stripped):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                item_text = re.sub(r"^\s*[-*]\s+", "", lines[i])
                items.append(f"<li>{item_text}</li>")
                i += 1
            processed.append(
                '<ul style="margin:4px 0; padding-left:20px;">'
                + "".join(items)
                + "</ul>"
            )
            continue

        # --- Ordered list (1. item) ----------------------------------------
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                item_text = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                items.append(f"<li>{item_text}</li>")
                i += 1
            processed.append(
                '<ol style="margin:4px 0; padding-left:20px;">'
                + "".join(items)
                + "</ol>"
            )
            continue

        # --- Regular line --------------------------------------------------
        processed.append(line)
        i += 1

    text = "<br>".join(processed)

    # --- Step 6: Restore inline code placeholders --------------------------
    for idx, html in enumerate(inline_codes):
        text = text.replace(f"\x00INLINECODE{idx}\x00", html)

    # --- Step 7: Restore code block placeholders ---------------------------
    for idx, html in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{idx}\x00", html)

    return text


# ---------------------------------------------------------------------------
# MessageBubble
# ---------------------------------------------------------------------------

class MessageBubble(QFrame):
    """Single chat message bubble."""

    bookmark_requested = pyqtSignal(str)  # raw text to bookmark
    bookmark_label_edit_requested = pyqtSignal(int, str)  # (bookmark_id, new_label)

    def __init__(self, role: str, text: str = "", parent=None):
        super().__init__(parent)
        self._role = role
        self._raw_text = text
        self._bookmark_id: int | None = None  # set externally if this message is bookmarked
        self._bookmark_label: str = ""
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

        # Bookmark label indicator (hidden by default)
        self._label_widget = QLabel("")
        self._label_widget.setStyleSheet(
            "font-size: 11px; color: #f9e2af; background: transparent; padding: 0 0 2px 0;"
        )
        self._label_widget.setVisible(False)
        layout.addWidget(self._label_widget)

        # Content display – QTextBrowser for rich HTML + link handling
        self._content = QTextBrowser()
        self._content.setOpenExternalLinks(True)
        self._content.setReadOnly(True)
        self._content.setFrameShape(QFrame.Shape.NoFrame)
        self._content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._content.setStyleSheet(
            "QTextBrowser { background: transparent; color: #cdd6f4; "
            "font-size: 13px; padding: 4px 0; border: none; }"
        )
        # Auto-resize to content
        self._content.document().contentsChanged.connect(self._adjust_height)
        layout.addWidget(self._content)

        # Set initial content
        if text:
            if role == "assistant":
                self._content.setHtml(markdown_to_html(text))
            else:
                self._content.setPlainText(text)

        # Right-click context menu for assistant messages
        if role == "assistant":
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)

    def _adjust_height(self):
        """Resize QTextBrowser to fit its document content."""
        doc_height = self._content.document().size().toSize().height()
        self._content.setFixedHeight(max(doc_height + 8, 20))

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        bookmark_action = menu.addAction("북마크 추가")
        copy_action = menu.addAction("전체 복사")
        save_action = menu.addAction("Word로 저장")

        label_action = None
        if self._bookmark_id is not None:
            menu.addSeparator()
            label_action = menu.addAction("라벨 편집")

        action = menu.exec(self.mapToGlobal(pos))
        if action is None:
            return
        if action == bookmark_action:
            self.bookmark_requested.emit(self._raw_text)
        elif action == copy_action:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._raw_text)
        elif action == save_action:
            self._save_as_word()
        elif label_action is not None and action == label_action:
            self._edit_bookmark_label()

    def _edit_bookmark_label(self):
        """Show an input dialog to edit the bookmark label."""
        new_label, ok = QInputDialog.getText(
            self,
            "라벨 편집",
            "북마크 라벨:",
            text=self._bookmark_label,
        )
        if ok and self._bookmark_id is not None:
            self._bookmark_label = new_label
            self.bookmark_label_edit_requested.emit(self._bookmark_id, new_label)
            self._update_label_display()

    def _update_label_display(self):
        """Show or hide the bookmark label widget."""
        if self._bookmark_label:
            self._label_widget.setText(f"[{self._bookmark_label}]")
            self._label_widget.setVisible(True)
        else:
            self._label_widget.setVisible(False)

    def _save_as_word(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getSaveFileName(self, "Word로 저장", "", "Word Files (*.docx)")
        if path:
            try:
                from core.document_io import save_to_word
                save_to_word(self._raw_text, path)
            except Exception as e:
                QMessageBox.warning(self, "저장 실패", f"Word 저장 중 오류:\n{e}")

    # --- Public API for text manipulation ---

    def append_text(self, text: str):
        """Append a streaming token (plain text mode)."""
        self._raw_text += text
        self._content.setPlainText(self._raw_text)

    def finish_render(self):
        """Re-render accumulated raw text as markdown HTML (call when streaming ends)."""
        if self._role == "assistant":
            self._content.setHtml(markdown_to_html(self._raw_text))

    def set_text(self, text: str):
        self._raw_text = text
        if self._role == "assistant":
            self._content.setHtml(markdown_to_html(text))
        else:
            self._content.setPlainText(text)

    def get_text(self) -> str:
        return self._raw_text

    def set_bookmark_info(self, bookmark_id: int, label: str = ""):
        """Mark this bubble as bookmarked with an optional label."""
        self._bookmark_id = bookmark_id
        self._bookmark_label = label
        self._update_label_display()


# ---------------------------------------------------------------------------
# ChatWidget
# ---------------------------------------------------------------------------

class ChatWidget(QScrollArea):
    """Scrollable chat area containing message bubbles."""

    bookmark_requested = pyqtSignal(str)  # bubble text to bookmark
    bookmark_label_changed = pyqtSignal(int, str)  # (bookmark_id, new_label)

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
        self._step_headers: list[QLabel] = []
        self._streaming_bubble: MessageBubble | None = None

    def add_message(self, role: str, text: str) -> MessageBubble:
        bubble = MessageBubble(role, text)
        bubble.bookmark_requested.connect(self.bookmark_requested.emit)
        bubble.bookmark_label_edit_requested.connect(self.bookmark_label_changed.emit)
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def start_streaming(self) -> MessageBubble:
        bubble = MessageBubble("assistant", "")
        bubble.bookmark_requested.connect(self.bookmark_requested.emit)
        bubble.bookmark_label_edit_requested.connect(self.bookmark_label_changed.emit)
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
            self._streaming_bubble.finish_render()
            text = self._streaming_bubble.get_text()
            self._streaming_bubble = None
        return text

    def clear_chat(self):
        for bubble in self._bubbles:
            self._layout.removeWidget(bubble)
            bubble.deleteLater()
        self._bubbles.clear()
        for header in self._step_headers:
            self._layout.removeWidget(header)
            header.deleteLater()
        self._step_headers.clear()
        self._streaming_bubble = None

    def add_step_header(self, step_name: str, step_index: int, total: int):
        """Add a visual step header for agent mode."""
        header = QLabel(f"Step {step_index + 1}/{total}: {step_name}")
        header.setStyleSheet(
            "color: #f9e2af; font-weight: bold; font-size: 13px; "
            "padding: 8px 12px; background-color: #313244; border-radius: 6px;"
        )
        self._layout.insertWidget(self._layout.count() - 1, header)
        self._step_headers.append(header)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(10, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))
