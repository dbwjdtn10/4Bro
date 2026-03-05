"""Settings dialog: API key configuration."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QMessageBox,
)
from PyQt6.QtCore import Qt

from core.engine import AIEngine


class SettingsDialog(QDialog):
    """API key and engine settings dialog."""

    def __init__(self, engine: AIEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self.setWindowTitle("4Bro 설정")
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Gemini API Key
        gemini_group = QGroupBox("Gemini API (1순위 - 필수)")
        gemini_layout = QVBoxLayout(gemini_group)

        gemini_desc = QLabel(
            "Google AI Studio에서 무료 발급:\n"
            "https://aistudio.google.com → Get API Key"
        )
        gemini_desc.setStyleSheet("color: #a6adc8; font-size: 11px;")
        gemini_desc.setWordWrap(True)
        gemini_layout.addWidget(gemini_desc)

        key_row1 = QHBoxLayout()
        self._gemini_input = QLineEdit()
        self._gemini_input.setPlaceholderText("Gemini API 키 입력...")
        self._gemini_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row1.addWidget(self._gemini_input, 1)

        self._gemini_status = QLabel("")
        self._gemini_status.setFixedWidth(80)
        key_row1.addWidget(self._gemini_status)
        gemini_layout.addLayout(key_row1)

        layout.addWidget(gemini_group)

        # Groq API Key
        groq_group = QGroupBox("Groq API (2순위 - 선택)")
        groq_layout = QVBoxLayout(groq_group)

        groq_desc = QLabel(
            "Groq에서 무료 발급:\n"
            "https://console.groq.com → API Keys"
        )
        groq_desc.setStyleSheet("color: #a6adc8; font-size: 11px;")
        groq_desc.setWordWrap(True)
        groq_layout.addWidget(groq_desc)

        key_row2 = QHBoxLayout()
        self._groq_input = QLineEdit()
        self._groq_input.setPlaceholderText("Groq API 키 입력 (선택사항)...")
        self._groq_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row2.addWidget(self._groq_input, 1)

        self._groq_status = QLabel("")
        self._groq_status.setFixedWidth(80)
        key_row2.addWidget(self._groq_status)
        groq_layout.addLayout(key_row2)

        layout.addWidget(groq_group)

        # Ollama info
        ollama_group = QGroupBox("Local Ollama (3순위 - 자동)")
        ollama_layout = QVBoxLayout(ollama_group)
        self._ollama_status = QLabel("확인 중...")
        ollama_layout.addWidget(self._ollama_status)
        layout.addWidget(ollama_group)

        # Check Ollama
        if self._engine.check_ollama():
            self._ollama_status.setText("Ollama 감지됨 (API 한도 초과 시 자동 전환)")
            self._ollama_status.setStyleSheet("color: #a6e3a1;")
        else:
            self._ollama_status.setText("Ollama 미설치 (선택사항 - ollama.com)")
            self._ollama_status.setStyleSheet("color: #a6adc8;")

        # Load existing keys (show masked)
        if self._engine.status.gemini_available:
            self._gemini_input.setPlaceholderText("(키 저장됨)")
            self._gemini_status.setText("활성")
            self._gemini_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")

        if self._engine.status.groq_available:
            self._groq_input.setPlaceholderText("(키 저장됨)")
            self._groq_status.setText("활성")
            self._groq_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")

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
        gemini_key = self._gemini_input.text().strip()
        groq_key = self._groq_input.text().strip()

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
