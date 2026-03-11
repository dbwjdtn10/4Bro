"""Settings dialog: API key configuration with change support."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QMessageBox,
)
from PyQt6.QtCore import Qt

from core.engine import AIEngine


def _mask_key(key: str) -> str:
    """Mask API key for display: 'AIza...xY9z'"""
    if not key:
        return ""
    if len(key) <= 4:
        return key[0] + "..." if len(key) >= 1 else "..."
    if len(key) <= 8:
        return key[:2] + "..." + key[-2:]
    return key[:4] + "..." + key[-4:]


class _KeyRow(QGroupBox):
    """Reusable API key input row with current key display and change button."""

    def __init__(self, title: str, desc: str, current_key: str, placeholder: str, parent=None):
        super().__init__(title, parent)
        self._current_key = current_key
        layout = QVBoxLayout(self)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Current key display row
        self._current_row = QHBoxLayout()

        self._current_label = QLabel("")
        self._current_label.setStyleSheet("color: #cdd6f4; font-size: 12px;")
        self._current_row.addWidget(self._current_label, 1)

        self._status_label = QLabel("")
        self._status_label.setFixedWidth(50)
        self._current_row.addWidget(self._status_label)

        self._change_btn = QPushButton("변경")
        self._change_btn.setObjectName("cancel_btn")
        self._change_btn.setFixedSize(50, 26)
        self._change_btn.clicked.connect(self._on_change)
        self._current_row.addWidget(self._change_btn)

        layout.addLayout(self._current_row)

        # New key input row (hidden by default if key exists)
        self._input_row = QHBoxLayout()

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        self._input_row.addWidget(self._input, 1)

        self._show_btn = QPushButton("보기")
        self._show_btn.setObjectName("cancel_btn")
        self._show_btn.setFixedSize(50, 26)
        self._show_btn.setCheckable(True)
        self._show_btn.toggled.connect(self._on_toggle_show)
        self._input_row.addWidget(self._show_btn)

        self._input_widget_container = []
        layout.addLayout(self._input_row)

        # Set initial state
        if current_key:
            self._current_label.setText(f"현재 키: {_mask_key(current_key)}")
            self._status_label.setText("활성")
            self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self._input.hide()
            self._show_btn.hide()
        else:
            self._current_label.setText("키 없음")
            self._current_label.setStyleSheet("color: #f38ba8; font-size: 12px;")
            self._status_label.setText("")
            self._change_btn.hide()

    def _on_change(self):
        self._input.show()
        self._show_btn.show()
        self._input.setFocus()
        self._change_btn.setText("취소")
        self._change_btn.clicked.disconnect()
        self._change_btn.clicked.connect(self._on_cancel_change)

    def _on_cancel_change(self):
        self._input.hide()
        self._show_btn.hide()
        self._input.clear()
        self._change_btn.setText("변경")
        self._change_btn.clicked.disconnect()
        self._change_btn.clicked.connect(self._on_change)

    def _on_toggle_show(self, checked: bool):
        if checked:
            self._input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_btn.setText("숨김")
        else:
            self._input.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_btn.setText("보기")

    def get_new_key(self) -> str:
        """Return new key if entered, empty string otherwise."""
        return self._input.text().strip()

    def has_existing_key(self) -> bool:
        return bool(self._current_key)


class SettingsDialog(QDialog):
    """API key and engine settings dialog."""

    def __init__(self, engine: AIEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self.setWindowTitle("4Bro 설정")
        self.setMinimumWidth(520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        saved = self._engine.get_saved_keys()

        # Gemini
        self._gemini_row = _KeyRow(
            title="Gemini API (1순위 - 필수)",
            desc="Google AI Studio에서 무료 발급:  https://aistudio.google.com → Get API Key",
            current_key=saved.get("gemini", ""),
            placeholder="새 Gemini API 키 입력...",
        )
        layout.addWidget(self._gemini_row)

        # Groq
        self._groq_row = _KeyRow(
            title="Groq API (2순위 - 선택)",
            desc="Groq에서 무료 발급:  https://console.groq.com → API Keys",
            current_key=saved.get("groq", ""),
            placeholder="새 Groq API 키 입력 (선택사항)...",
        )
        layout.addWidget(self._groq_row)

        # Ollama info
        ollama_group = QGroupBox("Local Ollama (3순위 - 자동)")
        ollama_layout = QVBoxLayout(ollama_group)
        self._ollama_status = QLabel("확인 중...")
        ollama_layout.addWidget(self._ollama_status)
        layout.addWidget(ollama_group)

        if self._engine.check_ollama():
            self._ollama_status.setText("Ollama 감지됨 (API 한도 초과 시 자동 전환)")
            self._ollama_status.setStyleSheet("color: #a6e3a1;")
        else:
            self._ollama_status.setText("Ollama 미설치 (선택사항 - ollama.com)")
            self._ollama_status.setStyleSheet("color: #a6adc8;")

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        gemini_key = self._gemini_row.get_new_key()
        groq_key = self._groq_row.get_new_key()

        if gemini_key:
            self._engine.setup_gemini(gemini_key)
        if groq_key:
            self._engine.setup_groq(groq_key)

        if not self._engine.status.gemini_available and not gemini_key:
            QMessageBox.warning(
                self, "알림",
                "Gemini API 키가 필요합니다.\n"
                "https://aistudio.google.com 에서 무료 발급 가능합니다."
            )
            return

        self.accept()
