"""QSS stylesheet for 4Bro v2.0 chat UI."""

from PyQt6.QtWidgets import QApplication

STYLESHEET = """
/* === Base === */
QMainWindow {
    background-color: #1e1e2e;
}

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "맑은 고딕", sans-serif;
    font-size: 13px;
}

/* === Inputs === */
QLineEdit, QTextEdit, QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
}

/* === Buttons === */
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #74c7ec;
}

QPushButton:pressed {
    background-color: #89dceb;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #585b70;
}

QPushButton#cancel_btn {
    background-color: #45475a;
    color: #cdd6f4;
}

QPushButton#cancel_btn:hover {
    background-color: #585b70;
}

/* === Send button === */
QPushButton#send_btn {
    background-color: #89b4fa;
    border-radius: 6px;
    font-size: 13px;
}

QPushButton#send_btn:disabled {
    background-color: #45475a;
}

/* === Attach button === */
QPushButton#attach_btn {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    font-size: 16px;
    padding: 0;
}

QPushButton#attach_btn:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

/* === Sidebar === */
QWidget#sidebar {
    background-color: #181825;
    border-right: 1px solid #313244;
}

QPushButton#new_chat_btn {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 10px;
    font-size: 13px;
}

QPushButton#new_chat_btn:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

/* === Chat area === */
QScrollArea#chat_area {
    background-color: #1e1e2e;
    border: none;
}

QWidget#chat_container {
    background-color: #1e1e2e;
}

/* === Message bubbles === */
QFrame#bubble_user {
    background-color: #313244;
    border-radius: 12px;
    border: none;
}

QFrame#bubble_assistant {
    background-color: #181825;
    border-radius: 12px;
    border: 1px solid #313244;
}

/* === Input bar === */
QWidget#input_bar {
    background-color: #1e1e2e;
    border-top: 1px solid #313244;
}

QTextEdit#chat_input {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px;
    font-size: 13px;
}

QTextEdit#chat_input:focus {
    border: 1px solid #89b4fa;
}

/* === Labels === */
QLabel {
    background-color: transparent;
    color: #a6adc8;
}

/* === Status bar === */
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
    font-size: 12px;
}

QStatusBar QLabel {
    padding: 0 8px;
}

/* === Lists === */
QListWidget {
    background-color: #181825;
    color: #a6adc8;
    border: 1px solid #313244;
    border-radius: 4px;
    font-size: 12px;
}

QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}

QListWidget::item:hover {
    background-color: #313244;
}

QListWidget::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}

/* === Scrollbar === */
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 8px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 0;
}

/* === Group boxes (settings) === */
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 8px;
    padding: 16px 12px 8px 12px;
    font-weight: bold;
    color: #cdd6f4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}

/* === Splitter === */
QSplitter::handle {
    background-color: #45475a;
    width: 1px;
}

/* === Mode selector === */
QComboBox#mode_selector {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 8px;
    min-width: 100px;
}
"""


def apply_stylesheet(app: QApplication):
    app.setStyleSheet(STYLESHEET)
