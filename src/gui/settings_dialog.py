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
    """API key settings dialog."""

    def __init__(self, engine: AIEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self.setWindowTitle("4Bro 설정")
        self.setMinimumWidth(600)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        saved = self._engine.get_saved_keys()

        # Gemini
        self._gemini_row = _KeyRow(
            title="Gemini API (필수)",
            desc="Google AI Studio에서 무료 발급:  https://aistudio.google.com → Get API Key",
            current_key=saved.get("gemini", ""),
            placeholder="새 Gemini API 키 입력...",
        )
        layout.addWidget(self._gemini_row)

        # Test API key button
        test_row = QHBoxLayout()
        test_row.addStretch()
        self._test_btn = QPushButton("API 키 테스트")
        self._test_btn.setObjectName("cancel_btn")
        self._test_btn.setFixedHeight(28)
        self._test_btn.clicked.connect(self._on_test_key)
        test_row.addWidget(self._test_btn)
        self._test_result = QLabel("")
        self._test_result.setStyleSheet("font-size: 11px;")
        test_row.addWidget(self._test_result)
        test_row.addStretch()
        layout.addLayout(test_row)

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

    def _on_test_key(self):
        """Test if the current or new API key works."""
        self._test_result.setText("테스트 중...")
        self._test_result.setStyleSheet("font-size: 11px; color: #f9e2af;")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # Use new key if entered, otherwise test existing
        new_key = self._gemini_row.get_new_key()
        if new_key:
            try:
                from core.api_client import GeminiClient
                client = GeminiClient(new_key)
                if client.is_available():
                    self._test_result.setText("\u2713 연결 성공!")
                    self._test_result.setStyleSheet("font-size: 11px; color: #a6e3a1;")
                else:
                    self._test_result.setText("\u2717 연결 실패 - 키를 확인해주세요")
                    self._test_result.setStyleSheet("font-size: 11px; color: #f38ba8;")
            except Exception as e:
                self._test_result.setText(f"\u2717 오류: {str(e)[:50]}")
                self._test_result.setStyleSheet("font-size: 11px; color: #f38ba8;")
        elif self._engine.status.gemini_available:
            self._test_result.setText("\u2713 현재 키 정상 작동 중")
            self._test_result.setStyleSheet("font-size: 11px; color: #a6e3a1;")
        else:
            self._test_result.setText("API 키를 먼저 입력해주세요")
            self._test_result.setStyleSheet("font-size: 11px; color: #f38ba8;")

    def _on_save(self):
        gemini_key = self._gemini_row.get_new_key()

        if gemini_key:
            self._engine.setup_gemini(gemini_key)

        if not self._engine.status.gemini_available and not gemini_key:
            QMessageBox.warning(
                self, "알림",
                "Gemini API 키가 필요합니다.\n"
                "https://aistudio.google.com 에서 무료 발급 가능합니다."
            )
            return

        self.accept()
