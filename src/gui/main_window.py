"""Main window: chat UI, agent workflows, DB history, projects, bookmarks,
image generation, search, drag-drop, and Word/PDF/txt export."""

from __future__ import annotations

import os
import base64
import tempfile
from datetime import datetime

import psutil
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStatusBar, QLabel, QComboBox, QMessageBox, QPushButton,
    QFileDialog, QMenu, QLineEdit, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QShortcut, QKeySequence

from core.engine import AIEngine
from core.database import Database
from core.logger import log
from core.version import VERSION
from core.prompts import get_system_prompt, build_chat_messages
from core.worker import StreamWorker
from core.agent import AGENT_WORKFLOWS, AgentWorker
from core.document_io import save_to_word, save_to_pdf, copy_to_clipboard
from gui.chat_widget import ChatWidget
from gui.input_bar import InputBar
from gui.sidebar import Sidebar


class ImageGenWorker(QThread):
    """Worker thread for image generation to avoid blocking the UI."""

    finished = pyqtSignal(object)  # result (bytes, path, or text)
    error = pyqtSignal(str)

    def __init__(self, engine: AIEngine, prompt: str, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._prompt = prompt

    def run(self):
        try:
            result = self._engine.generate_image(self._prompt)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """4Bro main window with chat and agent modes."""

    _MSG_PAGE_SIZE = 50
    _API_CONTEXT_LIMIT = 20  # max messages sent to AI for context
    _WELCOME_PREFIX = "안녕하세요"

    def __init__(self, engine: AIEngine, db: Database):
        super().__init__()
        self._engine = engine
        self._db = db
        self._worker: StreamWorker | None = None
        self._agent_worker: AgentWorker | None = None
        self._image_gen_worker: ImageGenWorker | None = None

        self._chat_history: list[dict] = []
        self._current_conv_id: int | None = None
        self._current_project_id: int | None = None
        self._mode: str = "ad_expert"

        # Message lazy-loading state
        self._msg_offset: int = 0
        self._has_more_msgs: bool = False

        # Message queue for sequential processing
        self._message_queue: list[tuple[str, str, list]] = []

        # Chat search state
        self._search_matches: list[int] = []  # indices into _chat_history
        self._search_current: int = -1

        self.setWindowTitle(f"4Bro v{VERSION} - AI 광고 어시스턴트")
        self.resize(1100, 750)
        self._settings = QSettings("4Bro", "MainWindow")
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.setAcceptDrops(True)
        self._init_ui()
        self._init_shortcuts()
        self._start_status_timer()
        self._sidebar.refresh_conversations(None)

    def _init_ui(self):
        """Build the main window layout: sidebar + right panel (top bar, chat, input)."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar(self._db)
        self._sidebar.new_chat_requested.connect(self._on_new_chat)
        self._sidebar.conversation_selected.connect(self._on_conv_selected)
        self._sidebar.conversation_deleted.connect(self._on_conv_deleted)
        self._sidebar.project_selected.connect(self._on_project_selected)
        self._sidebar.project_cleared.connect(self._on_project_cleared)
        self._sidebar.new_project_requested.connect(self._on_new_project)
        self._sidebar.edit_project_requested.connect(self._on_edit_project)
        self._sidebar.template_selected.connect(self._on_template_selected)
        main_layout.addWidget(self._sidebar)

        # Right content
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_bar.setFixedHeight(44)
        top_bar.setStyleSheet("background-color: #181825; border-bottom: 1px solid #313244;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 4, 16, 4)

        self._project_label = QLabel("")
        self._project_label.setStyleSheet("color: #f9e2af; font-size: 12px; font-weight: bold;")
        top_layout.addWidget(self._project_label)

        top_layout.addStretch()

        # Agent mode button
        agent_btn = QPushButton("에이전트")
        agent_btn.setObjectName("cancel_btn")
        agent_btn.setFixedHeight(28)
        agent_btn.clicked.connect(self._show_agent_menu)
        top_layout.addWidget(agent_btn)

        # Export button
        export_btn = QPushButton("내보내기")
        export_btn.setObjectName("cancel_btn")
        export_btn.setFixedHeight(28)
        export_btn.clicked.connect(self._on_export)
        top_layout.addWidget(export_btn)

        # Mode selector
        mode_label = QLabel("모드:")
        mode_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        top_layout.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.setObjectName("mode_selector")
        self._mode_combo.addItem("광고 전문가", "ad_expert")
        self._mode_combo.addItem("범용 어시스턴트", "general")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        top_layout.addWidget(self._mode_combo)

        settings_btn = QPushButton("설정")
        settings_btn.setObjectName("cancel_btn")
        settings_btn.setFixedHeight(28)
        settings_btn.clicked.connect(self._on_settings)
        top_layout.addWidget(settings_btn)

        right_layout.addWidget(top_bar)

        # Search bar (hidden by default, toggled with Ctrl+F)
        self._search_bar = QWidget()
        self._search_bar.setFixedHeight(38)
        self._search_bar.setStyleSheet(
            "background-color: #313244; border-bottom: 1px solid #45475a;"
        )
        search_layout = QHBoxLayout(self._search_bar)
        search_layout.setContentsMargins(12, 4, 12, 4)
        search_layout.setSpacing(6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("대화 검색...")
        self._search_input.setStyleSheet(
            "QLineEdit {"
            "  background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a;"
            "  border-radius: 4px; padding: 4px 8px; font-size: 12px;"
            "}"
            "QLineEdit:focus { border-color: #cba6f7; }"
        )
        self._search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self._search_input, 1)

        self._search_count_label = QLabel("")
        self._search_count_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        search_layout.addWidget(self._search_count_label)

        search_up_btn = QPushButton("\u25b2")
        search_up_btn.setFixedSize(28, 28)
        search_up_btn.setStyleSheet(
            "QPushButton { background-color: #45475a; color: #cdd6f4; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #585b70; }"
        )
        search_up_btn.clicked.connect(self._on_search_prev)
        search_layout.addWidget(search_up_btn)

        search_down_btn = QPushButton("\u25bc")
        search_down_btn.setFixedSize(28, 28)
        search_down_btn.setStyleSheet(
            "QPushButton { background-color: #45475a; color: #cdd6f4; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #585b70; }"
        )
        search_down_btn.clicked.connect(self._on_search_next)
        search_layout.addWidget(search_down_btn)

        search_close_btn = QPushButton("\u2715")
        search_close_btn.setFixedSize(28, 28)
        search_close_btn.setStyleSheet(
            "QPushButton { background-color: #45475a; color: #cdd6f4; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #f38ba8; }"
        )
        search_close_btn.clicked.connect(self._close_search)
        search_layout.addWidget(search_close_btn)

        self._search_bar.hide()
        right_layout.addWidget(self._search_bar)

        # "Load previous messages" button
        self._load_prev_btn = QPushButton("이전 메시지 불러오기")
        self._load_prev_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #313244; color: #cdd6f4; border: 1px solid #45475a;"
            "  border-radius: 4px; padding: 6px 12px; font-size: 11px; margin: 4px 16px;"
            "}"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._load_prev_btn.setFixedHeight(30)
        self._load_prev_btn.clicked.connect(self._on_load_prev_messages)
        self._load_prev_btn.hide()
        right_layout.addWidget(self._load_prev_btn)

        # Chat
        self._chat = ChatWidget()
        self._chat.bookmark_requested.connect(self._on_bookmark)
        self._chat.regenerate_requested.connect(self._on_regenerate)
        self._chat.edit_message_requested.connect(self._on_edit_message)
        right_layout.addWidget(self._chat, 1)

        # Queue status label
        self._queue_label = QLabel("")
        self._queue_label.setStyleSheet(
            "background-color: #313244; color: #f9e2af; font-size: 11px;"
            "padding: 4px 16px; border-top: 1px solid #45475a;"
        )
        self._queue_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._queue_label.hide()
        right_layout.addWidget(self._queue_label)

        # Input bar
        self._input_bar = InputBar()
        self._input_bar.message_sent.connect(self._on_message_sent)
        self._input_bar.image_gen_requested.connect(self._on_image_gen_requested)
        self._input_bar.stop_requested.connect(self._on_stop_requested)
        right_layout.addWidget(self._input_bar)

        main_layout.addWidget(right, 1)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._engine_label = QLabel("엔진: --")
        self._usage_label = QLabel("사용량: --")
        self._ram_label = QLabel("RAM: --")
        self._status_bar.addPermanentWidget(self._engine_label)
        self._status_bar.addPermanentWidget(self._usage_label)
        self._status_bar.addPermanentWidget(self._ram_label)

        welcome = (
            "안녕하세요! 4Bro입니다.\n\n"
            "광고 카피, 캠페인 기획, 매체별 변형 등 무엇이든 말씀해 주세요.\n\n"
            "**주요 기능:**\n"
            "- 상단 [에이전트] 버튼 \u2192 자동 워크플로우 실행\n"
            "- AI 응답 우클릭 \u2192 북마크/복사/Word 저장\n"
            "- Ctrl+F \u2192 대화 내 검색 | Ctrl+N \u2192 새 대화\n"
        )
        if not self._engine.status.gemini_available:
            welcome += "\n\u26a0\ufe0f Gemini API 키가 설정되지 않았습니다. 상단 [설정]에서 API 키를 먼저 입력해주세요."
        self._chat.add_message("assistant", welcome)
        self._update_engine_status()

    def _init_shortcuts(self):
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._toggle_search)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._on_new_chat)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._on_export)

    def keyPressEvent(self, event):
        """Close search bar on Escape."""
        if event.key() == Qt.Key.Key_Escape and self._search_bar.isVisible():
            self._close_search()
        else:
            super().keyPressEvent(event)

    # === Chat ===

    def _on_message_sent(self, text: str, doc_text: str, image_paths: list = None):
        """Handle a new message from the input bar; queue if worker is busy."""
        if self._worker and self._worker.isRunning():
            self._enqueue_message(text, doc_text, image_paths or [])
            return
        if self._agent_worker and self._agent_worker.isRunning():
            self._enqueue_message(text, doc_text, image_paths or [])
            return

        self._send_message(text, doc_text, image_paths)

    def _send_message(self, text: str, doc_text: str, image_paths: list = None):
        """Actually send a message to the AI engine."""
        image_paths = image_paths or []

        if self._current_conv_id is None:
            title = text[:30] + ("..." if len(text) > 30 else "")
            self._current_conv_id = self._db.create_conversation(
                title=title, project_id=self._current_project_id, mode=self._mode,
            )
            self._sidebar.refresh_conversations(self._current_project_id)
            self._sidebar.set_active_conversation(self._current_conv_id)

        self._db.add_message(self._current_conv_id, "user", text)

        display_text = text
        if image_paths:
            names = [os.path.basename(p) for p in image_paths]
            display_text = f"[이미지: {', '.join(names)}]\n\n{text}"

        self._chat.add_message("user", display_text)
        self._chat_history.append({"role": "user", "content": text})

        self._input_bar.set_enabled(False)
        self._chat.start_streaming()

        system_prompt = get_system_prompt(self._mode)
        if self._current_project_id:
            ctx = self._db.get_project_context(self._current_project_id)
            if ctx:
                system_prompt += f"\n\n{ctx}"

        # Limit context window to last N messages for API calls
        recent_history = self._chat_history[-(self._API_CONTEXT_LIMIT + 1):-1]
        messages = build_chat_messages(recent_history, text, doc_text)
        self._worker = StreamWorker(self._engine, messages, system_prompt, image_paths or None)
        self._worker.token_received.connect(self._on_token)
        self._worker.stream_finished.connect(self._on_stream_finished)
        self._worker.stream_error.connect(self._on_stream_error)
        self._worker.stream_cancelled.connect(self._on_stream_cancelled)
        self._worker.engine_switched.connect(lambda _: self._update_engine_status())
        self._worker.start()

    def _on_token(self, token: str):
        """Append a streaming token to the current bubble."""
        self._chat.append_stream_token(token)

    def _on_stream_finished(self, full_text: str):
        """Handle completed AI response."""
        self._chat.finish_streaming()
        self._chat_history.append({"role": "assistant", "content": full_text})
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()
        self._update_engine_status()
        if self._current_conv_id:
            self._db.add_message(self._current_conv_id, "assistant", full_text)

        self._process_message_queue()

    def _on_stream_cancelled(self):
        """Handle user-initiated stream cancellation."""
        self._chat.finish_streaming()
        # Remove orphaned user message so AI doesn't see unanswered question
        if self._chat_history and self._chat_history[-1]["role"] == "user":
            self._chat_history.pop()
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()

        self._process_message_queue()

    def _on_stream_error(self, error: str):
        """Handle streaming error with user-friendly messages."""
        self._chat.finish_streaming()
        log.error("Stream error: %s", error)

        # Parse error for user-friendly message
        err_lower = error.lower()
        if "invalid" in err_lower and "key" in err_lower:
            msg = "API 키가 올바르지 않습니다. [설정]에서 확인해주세요."
        elif "quota" in err_lower or "rate" in err_lower or "429" in error:
            msg = "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."
        elif "timeout" in err_lower or "timed out" in err_lower:
            msg = "응답 시간이 초과되었습니다. 인터넷 연결을 확인하고 다시 시도해주세요."
        elif "connection" in err_lower or "network" in err_lower or "urlopen" in err_lower:
            msg = "인터넷 연결에 문제가 있습니다. 네트워크를 확인해주세요."
        elif "permission" in err_lower or "403" in error:
            msg = "API 접근이 거부되었습니다. API 키 권한을 확인해주세요."
        elif "not found" in err_lower or "404" in error:
            msg = "API 모델을 찾을 수 없습니다. 잠시 후 다시 시도해주세요."
        elif "safety" in err_lower or "block" in err_lower:
            msg = "안전 필터에 의해 응답이 차단되었습니다. 다른 방식으로 질문해보세요."
        else:
            msg = f"오류가 발생했습니다:\n{error}"

        self._chat.add_message("assistant", msg)
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()
        self._process_message_queue()

    # === Message Queue ===

    def _enqueue_message(self, text: str, doc_text: str, image_paths: list):
        """Add a message to the queue when the worker is busy."""
        self._message_queue.append((text, doc_text, image_paths))
        count = len(self._message_queue)
        self._queue_label.setText(f"대기 중... ({count}개)")
        self._queue_label.show()
        self._status_bar.showMessage(f"메시지 대기열에 추가됨 ({count}개)", 3000)

    def _process_message_queue(self):
        """Send the next queued message if any."""
        if not self._message_queue:
            self._queue_label.hide()
            return

        text, doc_text, image_paths = self._message_queue.pop(0)
        count = len(self._message_queue)
        if count > 0:
            self._queue_label.setText(f"대기 중... ({count}개)")
        else:
            self._queue_label.hide()

        # Small delay to let UI settle before sending next message
        QTimer.singleShot(200, lambda: self._send_message(text, doc_text, image_paths))

    # === Agent Mode ===

    def _show_agent_menu(self):
        """Display a popup menu listing available agent workflows."""
        menu = QMenu(self)
        for wf_id, wf in AGENT_WORKFLOWS.items():
            action = menu.addAction(f"{wf.display_name} - {wf.description}")
            action.setData(wf_id)

        action = menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))
        if action:
            wf_id = action.data()
            self._start_agent(wf_id)

    def _start_agent(self, workflow_id: str):
        """Launch an agent workflow using the current input text."""
        wf = AGENT_WORKFLOWS.get(workflow_id)
        if not wf:
            return

        text = self._input_bar.get_text()
        if not text:
            QMessageBox.information(self, "알림", "작업 내용을 입력란에 먼저 입력해주세요.")
            return

        self._input_bar.clear_text()
        self._input_bar.set_enabled(False)

        # Create conversation
        if self._current_conv_id is None:
            title = f"[{wf.display_name}] {text[:20]}..."
            self._current_conv_id = self._db.create_conversation(
                title=title, project_id=self._current_project_id, mode=self._mode,
            )
            self._sidebar.refresh_conversations(self._current_project_id)

        self._db.add_message(self._current_conv_id, "user", f"[에이전트: {wf.display_name}] {text}")
        self._chat.add_message("user", f"[에이전트: {wf.display_name}]\n{text}")
        self._chat_history.append({"role": "user", "content": f"[에이전트: {wf.display_name}] {text}"})
        self._chat.add_message("assistant", f"'{wf.display_name}' 워크플로우를 시작합니다. ({len(wf.steps)}단계)")

        system_prompt = get_system_prompt(self._mode)
        if self._current_project_id:
            ctx = self._db.get_project_context(self._current_project_id)
            if ctx:
                system_prompt += f"\n\n{ctx}"

        # Web search will run in AgentWorker thread (non-blocking)
        search_query = text if workflow_id == "competitor_research" else ""

        self._agent_worker = AgentWorker(
            self._engine, wf, text, system_prompt, search_query=search_query,
        )
        self._agent_worker.step_started.connect(
            lambda i, name: self._on_agent_step_started(i, name, len(wf.steps))
        )
        self._agent_worker.token_received.connect(self._on_agent_token)
        self._agent_worker.step_completed.connect(self._on_agent_step_completed)
        self._agent_worker.workflow_finished.connect(self._on_agent_finished)
        self._agent_worker.workflow_error.connect(self._on_agent_error)
        self._agent_worker.start()

    def _on_agent_step_started(self, index: int, name: str, total: int):
        """Display a step header and begin streaming for the step."""
        self._chat.add_step_header(name, index, total)
        self._chat.start_streaming()
        self._status_bar.showMessage(f"Step {index + 1}/{total}: {name}")

    def _on_agent_token(self, index: int, token: str):
        """Forward agent streaming tokens to the chat widget."""
        self._chat.append_stream_token(token)

    def _on_agent_step_completed(self, index: int, name: str, full_text: str):
        """Finalize display for a completed agent step."""
        self._chat.finish_streaming()
        self._update_engine_status()

    def _on_agent_finished(self, combined_text: str):
        """Handle agent workflow completion: auto-save and update UI."""
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()

        # Auto-save to Word
        saved_path = self._auto_save_agent(combined_text)
        if saved_path:
            self._sidebar.add_recent_file(saved_path)
            self._chat.add_message("assistant", f"완료! Word로 자동 저장되었습니다:\n{saved_path}")
            self._status_bar.showMessage(f"저장됨: {saved_path}", 5000)
        else:
            self._chat.add_message("assistant", "워크플로우가 완료되었습니다.")

        if self._current_conv_id:
            self._db.add_message(self._current_conv_id, "assistant", combined_text)

        self._chat_history.append({"role": "assistant", "content": combined_text})
        self._agent_worker = None

        self._process_message_queue()

    def _on_agent_error(self, error: str):
        """Handle agent workflow error with user-friendly messages."""
        log.error("Agent error: %s", error)
        err_lower = error.lower()
        if "timeout" in err_lower or "connection" in err_lower:
            msg = "에이전트 실행 중 네트워크 오류가 발생했습니다. 인터넷 연결을 확인해주세요."
        elif "key" in err_lower or "auth" in err_lower:
            msg = "에이전트 실행 중 API 인증 오류가 발생했습니다. 설정에서 API 키를 확인해주세요."
        else:
            msg = f"에이전트 실행 중 오류가 발생했습니다:\n{error}\n\n다시 시도하거나, 입력을 수정해보세요."
        self._chat.add_message("assistant", msg)
        self._input_bar.set_enabled(True)
        self._agent_worker = None
        self._process_message_queue()

    def _auto_save_agent(self, text: str) -> str:
        """Auto-save agent output to a Word file. Returns the saved path or ''."""
        try:
            docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "4Bro")
            if self._current_project_id:
                proj = self._db.get_project(self._current_project_id)
                if proj:
                    docs_dir = os.path.join(docs_dir, proj["name"])
            os.makedirs(docs_dir, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
            filepath = os.path.join(docs_dir, f"agent_{date_str}.docx")
            save_to_word(text, filepath)
            return filepath
        except Exception as e:
            log.error("Agent auto-save failed: %s", e)
            self._status_bar.showMessage(f"Word 자동 저장 실패: {e}", 5000)
            return ""

    # === Image Generation ===

    def _on_image_gen_requested(self, prompt: str):
        """Handle image generation request from input bar."""
        if self._image_gen_worker and self._image_gen_worker.isRunning():
            self._status_bar.showMessage("이미지 생성이 이미 진행 중입니다.", 3000)
            return

        if self._current_conv_id is None:
            title = f"[이미지] {prompt[:25]}..."
            self._current_conv_id = self._db.create_conversation(
                title=title, project_id=self._current_project_id, mode=self._mode,
            )
            self._sidebar.refresh_conversations(self._current_project_id)
            self._sidebar.set_active_conversation(self._current_conv_id)

        self._chat.add_message("user", f"[이미지 생성] {prompt}")
        self._chat_history.append({"role": "user", "content": f"[이미지 생성] {prompt}"})
        self._db.add_message(self._current_conv_id, "user", f"[이미지 생성] {prompt}")

        self._chat.add_message("assistant", "이미지를 생성하고 있습니다...")
        self._input_bar.set_enabled(False)
        self._status_bar.showMessage("이미지 생성 중...", 0)

        self._image_gen_worker = ImageGenWorker(self._engine, prompt)
        self._image_gen_worker.finished.connect(self._on_image_gen_finished)
        self._image_gen_worker.error.connect(self._on_image_gen_error)
        self._image_gen_worker.start()

    def _on_image_gen_finished(self, result):
        """Handle completed image generation."""
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()
        self._status_bar.showMessage("이미지 생성 완료!", 3000)

        response_text = ""

        if isinstance(result, bytes):
            # Raw image bytes -- save to temp file and show path
            temp_dir = os.path.join(tempfile.gettempdir(), "4bro_images")
            os.makedirs(temp_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            img_path = os.path.join(temp_dir, f"generated_{ts}.png")
            with open(img_path, "wb") as f:
                f.write(result)
            response_text = f"이미지가 생성되었습니다!\n\n저장 위치: {img_path}"
        elif isinstance(result, str):
            # Could be a file path, URL, or base64 string
            if os.path.isfile(result):
                response_text = f"이미지가 생성되었습니다!\n\n저장 위치: {result}"
            elif result.startswith("http"):
                response_text = f"이미지가 생성되었습니다!\n\nURL: {result}"
            elif len(result) > 200:
                # Likely base64 data -- save to file
                try:
                    img_data = base64.b64decode(result)
                    temp_dir = os.path.join(tempfile.gettempdir(), "4bro_images")
                    os.makedirs(temp_dir, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    img_path = os.path.join(temp_dir, f"generated_{ts}.png")
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    response_text = f"이미지가 생성되었습니다!\n\n저장 위치: {img_path}"
                except Exception:
                    response_text = f"이미지 생성 결과:\n{result[:500]}"
            else:
                response_text = f"이미지 생성 결과:\n{result}"
        else:
            response_text = f"이미지 생성 결과:\n{str(result)}"

        self._chat.add_message("assistant", response_text)
        self._chat_history.append({"role": "assistant", "content": response_text})
        if self._current_conv_id:
            self._db.add_message(self._current_conv_id, "assistant", response_text)

        self._image_gen_worker = None

    def _on_image_gen_error(self, error: str):
        """Handle image generation error."""
        log.error("Image generation failed: %s", error)
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()
        self._status_bar.showMessage("이미지 생성 실패", 3000)

        error_text = f"이미지 생성 중 오류가 발생했습니다:\n{error}"
        self._chat.add_message("assistant", error_text)
        self._chat_history.append({"role": "assistant", "content": error_text})
        if self._current_conv_id:
            self._db.add_message(self._current_conv_id, "assistant", error_text)

        self._image_gen_worker = None

    # === Chat Search ===

    def _toggle_search(self):
        """Toggle the search bar visibility."""
        if self._search_bar.isVisible():
            self._close_search()
        else:
            self._search_bar.show()
            self._search_input.setFocus()
            self._search_input.selectAll()

    def _close_search(self):
        """Hide the search bar and clear search state."""
        self._search_bar.hide()
        self._search_input.clear()
        self._search_matches = []
        self._search_current = -1
        self._search_count_label.setText("")
        self._input_bar.set_focus()

    def _on_search_text_changed(self, text: str):
        """Search through chat history when search text changes."""
        self._search_matches = []
        self._search_current = -1

        if not text.strip():
            self._search_count_label.setText("")
            return

        query = text.strip().lower()
        for i, msg in enumerate(self._chat_history):
            if query in msg["content"].lower():
                self._search_matches.append(i)

        if self._search_matches:
            self._search_current = 0
            self._update_search_display()
        else:
            self._search_count_label.setText("0개 발견")

    def _on_search_next(self):
        """Navigate to the next search match."""
        if not self._search_matches:
            return
        self._search_current = (self._search_current + 1) % len(self._search_matches)
        self._update_search_display()

    def _on_search_prev(self):
        """Navigate to the previous search match."""
        if not self._search_matches:
            return
        self._search_current = (self._search_current - 1) % len(self._search_matches)
        self._update_search_display()

    def _update_search_display(self):
        """Update the search count label and scroll to the current match."""
        total = len(self._search_matches)
        current = self._search_current + 1
        self._search_count_label.setText(f"{current}/{total}개 발견")

        match_idx = self._search_matches[self._search_current]
        try:
            self._chat.scroll_to_message(match_idx)
        except (AttributeError, IndexError):
            try:
                self._chat.highlight_message(match_idx, self._search_input.text())
            except (AttributeError, IndexError):
                pass

    # === Stop / Regenerate / Edit / Template / Drag-Drop ===

    def _on_stop_requested(self):
        """Cancel current generation."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        if self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.cancel()
        if self._image_gen_worker and self._image_gen_worker.isRunning():
            self._image_gen_worker.terminate()
        self._input_bar.set_enabled(True)
        self._status_bar.showMessage("생성이 중지되었습니다.", 3000)

    def _on_regenerate(self):
        """Regenerate the last assistant response."""
        if self._worker and self._worker.isRunning():
            return  # Already generating

        # Find the last user message to resend
        last_user_msg = None
        last_user_idx = -1
        for i in range(len(self._chat_history) - 1, -1, -1):
            if self._chat_history[i]["role"] == "user":
                last_user_msg = self._chat_history[i]["content"]
                last_user_idx = i
                break

        if last_user_msg is None:
            return

        # Remove the last assistant response from history (if it exists after the user msg)
        if last_user_idx < len(self._chat_history) - 1:
            self._chat_history = self._chat_history[:last_user_idx + 1]

        # Remove the last assistant bubble from chat display
        try:
            self._chat.remove_last_assistant_bubble()
        except AttributeError:
            pass

        # Resend the last user message
        self._input_bar.set_enabled(False)
        self._chat.start_streaming()

        system_prompt = get_system_prompt(self._mode)
        if self._current_project_id:
            ctx = self._db.get_project_context(self._current_project_id)
            if ctx:
                system_prompt += f"\n\n{ctx}"

        recent_history = self._chat_history[-(self._API_CONTEXT_LIMIT + 1):-1]
        messages = build_chat_messages(recent_history, last_user_msg)
        self._worker = StreamWorker(self._engine, messages, system_prompt)
        self._worker.token_received.connect(self._on_token)
        self._worker.stream_finished.connect(self._on_stream_finished)
        self._worker.stream_error.connect(self._on_stream_error)
        self._worker.stream_cancelled.connect(self._on_stream_cancelled)
        self._worker.start()

    def _on_edit_message(self, original_text: str):
        """Put the original message text back into the input bar for editing."""
        self._input_bar.set_text(original_text)
        self._input_bar.set_focus()
        self._status_bar.showMessage("메시지를 수정한 후 다시 전송하세요.", 3000)

    def _on_template_selected(self, text: str):
        """Insert template text into the input bar."""
        current = self._input_bar.get_text()
        if current:
            self._input_bar.set_text(current + "\n\n" + text)
        else:
            self._input_bar.set_text(text)
        self._input_bar.set_focus()
        self._status_bar.showMessage("템플릿이 입력란에 추가되었습니다.", 3000)

    def dragEnterEvent(self, event):
        """Accept drag events containing file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        """Handle file drops - attach to input bar."""
        if not event.mimeData().hasUrls():
            return

        from core.document_io import SUPPORTED_EXTENSIONS, read_document

        image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        image_paths = []
        doc_paths = []

        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path or not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext in image_exts:
                image_paths.append(path)
            elif ext in SUPPORTED_EXTENSIONS:
                doc_paths.append(path)

        # Process documents
        if doc_paths:
            errors = []
            for path in doc_paths:
                try:
                    text = read_document(path)
                    filename = os.path.basename(path)
                    self._input_bar._doc_texts.append((filename, text))
                except Exception:
                    errors.append(os.path.basename(path))
            self._input_bar._update_attach_label()
            if errors:
                self._status_bar.showMessage(f"첨부 실패: {', '.join(errors)}", 3000)

        # Process images
        if image_paths:
            self._input_bar._image_paths.extend(image_paths)
            names = [os.path.basename(p) for p in self._input_bar._image_paths]
            self._input_bar._image_label.setText(f"\U0001f5bc {', '.join(names)}  [x]")
            self._input_bar._image_label.show()
            self._input_bar._image_label.mousePressEvent = lambda e: self._input_bar._clear_images()

        if doc_paths or image_paths:
            total = len(doc_paths) + len(image_paths)
            self._status_bar.showMessage(f"{total}개 파일이 첨부되었습니다.", 3000)
            self._input_bar.set_focus()

        event.acceptProposedAction()

    # === Bookmarks ===

    def _on_bookmark(self, text: str):
        """Save a message to bookmarks."""
        self._db.add_bookmark(
            content=text,
            conversation_id=self._current_conv_id,
            project_id=self._current_project_id,
        )
        self._status_bar.showMessage("북마크에 추가되었습니다.", 3000)

    # === Export ===

    def _on_export(self):
        """Show export options menu."""
        menu = QMenu(self)
        word_action = menu.addAction("현재 대화 Word로 저장")
        txt_action = menu.addAction("현재 대화 txt로 저장")
        pdf_action = menu.addAction("현재 대화 PDF로 저장")
        clipboard_action = menu.addAction("클립보드 복사")
        menu.addSeparator()
        bookmark_action = menu.addAction("북마크 모아보기 Word")

        action = menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))
        if action == word_action:
            self._export_chat("docx")
        elif action == txt_action:
            self._export_chat("txt")
        elif action == pdf_action:
            self._export_chat("pdf")
        elif action == clipboard_action:
            self._export_clipboard()
        elif action == bookmark_action:
            self._export_bookmarks()

    def _export_chat(self, fmt: str):
        """Export current chat history in the specified format."""
        if not self._chat_history:
            QMessageBox.information(self, "알림", "내보낼 대화가 없습니다.")
            return

        text = "\n\n".join(
            f"{'[나]' if m['role'] == 'user' else '[4Bro]'}\n{m['content']}"
            for m in self._chat_history
        )

        if fmt == "docx":
            path, _ = QFileDialog.getSaveFileName(self, "Word로 저장", "", "Word Files (*.docx)")
            if path:
                save_to_word(text, path)
                self._sidebar.add_recent_file(path)
                self._status_bar.showMessage(f"저장됨: {path}", 3000)
        elif fmt == "pdf":
            path, _ = QFileDialog.getSaveFileName(self, "PDF로 저장", "", "PDF Files (*.pdf)")
            if path:
                try:
                    save_to_pdf(self._chat_history, path)
                    self._sidebar.add_recent_file(path)
                    self._status_bar.showMessage(f"PDF 저장됨: {path}", 3000)
                except Exception as e:
                    log.error("PDF export failed: %s", e)
                    QMessageBox.warning(self, "오류", f"PDF 저장 실패:\n{e}")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "텍스트로 저장", "", "Text Files (*.txt)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self._sidebar.add_recent_file(path)

    def _export_clipboard(self):
        """Copy current conversation to clipboard as markdown."""
        if not self._chat_history:
            QMessageBox.information(self, "알림", "복사할 대화가 없습니다.")
            return
        copy_to_clipboard(self._chat_history)
        self._status_bar.showMessage("대화가 클립보드에 복사되었습니다.", 3000)

    def _export_bookmarks(self):
        """Export all bookmarks for the current project to a Word file."""
        bookmarks = self._db.list_bookmarks(self._current_project_id)
        if not bookmarks:
            QMessageBox.information(self, "알림", "저장된 북마크가 없습니다.")
            return

        text = "# 북마크 모음\n\n"
        for bm in bookmarks:
            text += f"---\n{bm['content']}\n\n"

        path, _ = QFileDialog.getSaveFileName(self, "북마크 Word 저장", "", "Word Files (*.docx)")
        if path:
            save_to_word(text, path)
            self._sidebar.add_recent_file(path)
            self._status_bar.showMessage(f"북마크 저장됨: {path}", 3000)

    # === Conversations (lazy-load messages) ===

    def _on_new_chat(self):
        """Start a fresh conversation."""
        self._current_conv_id = None
        self._chat_history = []
        self._msg_offset = 0
        self._has_more_msgs = False
        self._load_prev_btn.hide()
        self._chat.clear_chat()
        self._chat.add_message("assistant", "새 대화를 시작합니다. 무엇을 도와드릴까요?")

    def _on_conv_deleted(self, conv_id: int):
        """Handle conversation deletion from sidebar."""
        if conv_id == self._current_conv_id:
            self._on_new_chat()
            self._status_bar.showMessage("대화가 삭제되었습니다.", 3000)

    def _on_conv_selected(self, conv_id: int):
        """Load and display a conversation selected from the sidebar."""
        if conv_id == self._current_conv_id:
            return
        if self._search_bar.isVisible():
            self._close_search()
        self._current_conv_id = conv_id
        self._chat_history = []
        self._chat.clear_chat()

        # Load only the last N messages initially
        messages = self._db.get_messages(conv_id, limit=self._MSG_PAGE_SIZE)

        # Check if there are more messages beyond what we loaded
        try:
            total = self._db.count_messages(conv_id)
            self._has_more_msgs = total > len(messages)
            self._msg_offset = len(messages)
        except (AttributeError, TypeError):
            self._has_more_msgs = len(messages) >= self._MSG_PAGE_SIZE
            self._msg_offset = len(messages)

        if self._has_more_msgs:
            self._load_prev_btn.show()
        else:
            self._load_prev_btn.hide()

        for msg in messages:
            self._chat.add_message(msg["role"], msg["content"])
            self._chat_history.append({"role": msg["role"], "content": msg["content"]})

        conv = self._db.get_conversation(conv_id)
        if conv:
            if conv.get("project_id"):
                self._current_project_id = conv["project_id"]
                proj = self._db.get_project(self._current_project_id)
                if proj:
                    self._project_label.setText(f"프로젝트: {proj['name']}")
            # Restore conversation mode
            saved_mode = conv.get("mode", "ad_expert")
            self._mode = saved_mode
            idx = self._mode_combo.findData(saved_mode)
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)

        self._sidebar.set_active_conversation(conv_id)

    def _on_load_prev_messages(self):
        """Load older messages and prepend them to the chat."""
        if not self._current_conv_id or not self._has_more_msgs:
            return

        older_messages = self._db.get_messages(
            self._current_conv_id,
            limit=self._MSG_PAGE_SIZE,
            offset=self._msg_offset,
        )

        if not older_messages:
            self._has_more_msgs = False
            self._load_prev_btn.hide()
            return

        # Prepend older messages to chat history
        new_history = []
        for msg in older_messages:
            new_history.append({"role": msg["role"], "content": msg["content"]})

        new_count = len(older_messages)
        self._chat_history = new_history + self._chat_history

        # Rebuild the chat display
        self._chat.clear_chat()
        for msg in self._chat_history:
            self._chat.add_message(msg["role"], msg["content"])

        self._msg_offset += new_count

        # Check if there are still more messages
        try:
            total = self._db.count_messages(self._current_conv_id)
            self._has_more_msgs = self._msg_offset < total
        except (AttributeError, TypeError):
            self._has_more_msgs = len(older_messages) >= self._MSG_PAGE_SIZE

        if not self._has_more_msgs:
            self._load_prev_btn.hide()

        # Scroll to where user was (approximately) after layout settles
        try:
            QTimer.singleShot(50, lambda: self._chat.scroll_to_message_index(new_count))
        except (AttributeError, TypeError):
            pass

        self._status_bar.showMessage(
            f"이전 메시지 {new_count}개를 불러왔습니다.", 3000
        )

    # === Projects ===

    def _on_project_selected(self, project_id: int):
        """Switch to the selected project and filter conversations."""
        self._current_project_id = project_id
        proj = self._db.get_project(project_id)
        if proj:
            self._project_label.setText(f"프로젝트: {proj['name']}")
            self._status_bar.showMessage(f"프로젝트 '{proj['name']}' 선택됨", 3000)
        self._sidebar.refresh_conversations(project_id)

    def _on_project_cleared(self):
        """Clear project filter and show all conversations."""
        self._current_project_id = None
        self._project_label.setText("")
        self._sidebar.refresh_conversations(None)

    def _on_new_project(self):
        """Open the project creation dialog."""
        from gui.project_dialog import ProjectDialog
        dialog = ProjectDialog(self._db, parent=self)
        if dialog.exec() == 1:
            self._sidebar.refresh_projects()
            if dialog.project_id:
                self._on_project_selected(dialog.project_id)

    def _on_edit_project(self, project_id: int):
        """Open the project editing dialog."""
        from gui.project_dialog import ProjectDialog
        dialog = ProjectDialog(self._db, project_id=project_id, parent=self)
        result = dialog.exec()
        if result == 2:
            self._on_project_cleared()
        self._sidebar.refresh_projects()

    # === Mode / Settings ===

    def _on_mode_changed(self, idx: int):
        """Handle AI mode change (ad expert / general)."""
        self._mode = self._mode_combo.itemData(idx)
        self._status_bar.showMessage(f"모드 변경: {self._mode_combo.currentText()}", 3000)

    def _on_settings(self):
        """Open the settings dialog."""
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._engine, self)
        if dialog.exec():
            self._update_engine_status()
            self._status_bar.showMessage("설정이 저장되었습니다.", 3000)

    # === Status ===

    def _update_engine_status(self):
        """Refresh the engine and usage labels in the status bar."""
        self._engine_label.setText(f"엔진: {self._engine.get_current_engine_name()}")
        self._usage_label.setText(f"사용량: {self._engine.get_usage_text()}")

    def _start_status_timer(self):
        """Start periodic RAM usage monitoring."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_resource_status)
        self._timer.start(5000)

    def _update_resource_status(self):
        """Update the RAM usage display in the status bar."""
        ram = psutil.virtual_memory()
        self._ram_label.setText(f"RAM: {ram.used / (1024**3):.1f}/{ram.total / (1024**3):.1f}GB")

    def closeEvent(self, event):
        """Persist window geometry and clean up workers on close."""
        self._settings.setValue("geometry", self.saveGeometry())
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        if self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.cancel()
            self._agent_worker.wait(3000)
        if self._image_gen_worker and self._image_gen_worker.isRunning():
            self._image_gen_worker.wait(3000)
        self._db.close()
        super().closeEvent(event)
