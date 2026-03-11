"""Main window: chat + agent mode, DB history, projects, bookmarks, Word export."""

from __future__ import annotations

import os
from datetime import datetime

import psutil
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStatusBar, QLabel, QComboBox, QMessageBox, QPushButton,
    QFileDialog, QMenu,
)
from PyQt6.QtCore import Qt, QTimer

from core.engine import AIEngine
from core.database import Database
from core.version import VERSION
from core.prompts import get_system_prompt, build_chat_messages
from core.worker import StreamWorker
from core.agent import AGENT_WORKFLOWS, AgentWorker
from core.document_io import save_to_word
from gui.chat_widget import ChatWidget
from gui.input_bar import InputBar
from gui.sidebar import Sidebar


class MainWindow(QMainWindow):
    """4Bro main window with chat and agent modes."""

    def __init__(self, engine: AIEngine, db: Database):
        super().__init__()
        self._engine = engine
        self._db = db
        self._worker: StreamWorker | None = None
        self._agent_worker: AgentWorker | None = None

        self._chat_history: list[dict] = []
        self._current_conv_id: int | None = None
        self._current_project_id: int | None = None
        self._mode: str = "ad_expert"

        self.setWindowTitle(f"4Bro v{VERSION} - AI 광고 어시스턴트")
        self.resize(1100, 750)
        self._init_ui()
        self._start_status_timer()
        self._sidebar.refresh_conversations(None)

    def _init_ui(self):
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

        # Chat
        self._chat = ChatWidget()
        self._chat.bookmark_requested.connect(self._on_bookmark)
        right_layout.addWidget(self._chat, 1)

        # Input bar
        self._input_bar = InputBar()
        self._input_bar.message_sent.connect(self._on_message_sent)
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

        self._chat.add_message(
            "assistant",
            "안녕하세요! 4Bro입니다.\n\n"
            "광고 카피, 캠페인 기획, 매체별 변형 등 무엇이든 말씀해 주세요.\n\n"
            "상단 [에이전트] 버튼으로 자동 워크플로우도 실행할 수 있습니다.\n"
            "AI 응답을 우클릭하면 북마크/복사/Word 저장이 가능합니다."
        )
        self._update_engine_status()

    # === Chat ===

    def _on_message_sent(self, text: str, doc_text: str, image_paths: list = None):
        if self._worker and self._worker.isRunning():
            return
        if self._agent_worker and self._agent_worker.isRunning():
            return

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

        # Warn user if input is very long
        if len(text) > 60000 or len(doc_text) > 80000:
            display_text += "\n\n⚠️ 텍스트가 매우 길어 일부만 AI에게 전달됩니다."

        self._chat.add_message("user", display_text)
        self._chat_history.append({"role": "user", "content": text})

        self._input_bar.set_enabled(False)
        self._chat.start_streaming()

        system_prompt = get_system_prompt(self._mode)
        if self._current_project_id:
            ctx = self._db.get_project_context(self._current_project_id)
            if ctx:
                system_prompt += f"\n\n{ctx}"

        messages = build_chat_messages(self._chat_history[:-1], text, doc_text)
        self._worker = StreamWorker(self._engine, messages, system_prompt, image_paths or None)
        self._worker.token_received.connect(self._on_token)
        self._worker.stream_finished.connect(self._on_stream_finished)
        self._worker.stream_error.connect(self._on_stream_error)
        self._worker.stream_cancelled.connect(self._on_stream_cancelled)
        self._worker.engine_switched.connect(lambda _: self._update_engine_status())
        self._worker.start()

    def _on_token(self, token: str):
        self._chat.append_stream_token(token)

    def _on_stream_finished(self, full_text: str):
        self._chat.finish_streaming()
        self._chat_history.append({"role": "assistant", "content": full_text})
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()
        self._update_engine_status()
        if self._current_conv_id:
            self._db.add_message(self._current_conv_id, "assistant", full_text)

    def _on_stream_cancelled(self):
        self._chat.finish_streaming()
        # Remove orphaned user message so AI doesn't see unanswered question
        if self._chat_history and self._chat_history[-1]["role"] == "user":
            self._chat_history.pop()
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()

    def _on_stream_error(self, error: str):
        self._chat.finish_streaming()
        self._chat.add_message("assistant", f"오류가 발생했습니다:\n{error}\n\n설정에서 API 키를 확인해 주세요.")
        self._input_bar.set_enabled(True)
        self._input_bar.set_focus()

    # === Agent Mode ===

    def _show_agent_menu(self):
        menu = QMenu(self)
        for wf_id, wf in AGENT_WORKFLOWS.items():
            action = menu.addAction(f"{wf.display_name} - {wf.description}")
            action.setData(wf_id)

        action = menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))
        if action:
            wf_id = action.data()
            self._start_agent(wf_id)

    def _start_agent(self, workflow_id: str):
        wf = AGENT_WORKFLOWS.get(workflow_id)
        if not wf:
            return

        # Get user input from input bar
        text = self._input_bar._input.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "알림", "작업 내용을 입력란에 먼저 입력해주세요.")
            return

        self._input_bar._input.clear()
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
        self._chat.add_step_header(name, index, total)
        self._chat.start_streaming()
        self._status_bar.showMessage(f"Step {index + 1}/{total}: {name}")

    def _on_agent_token(self, index: int, token: str):
        self._chat.append_stream_token(token)

    def _on_agent_step_completed(self, index: int, name: str, full_text: str):
        self._chat.finish_streaming()
        self._update_engine_status()

    def _on_agent_finished(self, combined_text: str):
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

    def _on_agent_error(self, error: str):
        self._chat.add_message("assistant", f"에이전트 오류:\n{error}")
        self._input_bar.set_enabled(True)
        self._agent_worker = None

    def _auto_save_agent(self, text: str) -> str:
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
        except Exception:
            return ""

    # === Bookmarks ===

    def _on_bookmark(self, text: str):
        self._db.add_bookmark(
            content=text,
            conversation_id=self._current_conv_id,
            project_id=self._current_project_id,
        )
        self._status_bar.showMessage("북마크에 추가되었습니다.", 3000)

    # === Export ===

    def _on_export(self):
        menu = QMenu(self)
        word_action = menu.addAction("현재 대화 Word로 저장")
        txt_action = menu.addAction("현재 대화 txt로 저장")
        bookmark_action = menu.addAction("북마크 모아보기 Word")

        action = menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))
        if action == word_action:
            self._export_chat("docx")
        elif action == txt_action:
            self._export_chat("txt")
        elif action == bookmark_action:
            self._export_bookmarks()

    def _export_chat(self, fmt: str):
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
        else:
            path, _ = QFileDialog.getSaveFileName(self, "텍스트로 저장", "", "Text Files (*.txt)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self._sidebar.add_recent_file(path)

    def _export_bookmarks(self):
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

    # === Conversations ===

    def _on_new_chat(self):
        self._current_conv_id = None
        self._chat_history = []
        self._chat.clear_chat()
        self._chat.add_message("assistant", "새 대화를 시작합니다. 무엇을 도와드릴까요?")

    def _on_conv_deleted(self, conv_id: int):
        if conv_id == self._current_conv_id:
            self._on_new_chat()

    def _on_conv_selected(self, conv_id: int):
        if conv_id == self._current_conv_id:
            return
        self._current_conv_id = conv_id
        self._chat_history = []
        self._chat.clear_chat()

        for msg in self._db.get_messages(conv_id):
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

    # === Projects ===

    def _on_project_selected(self, project_id: int):
        self._current_project_id = project_id
        proj = self._db.get_project(project_id)
        if proj:
            self._project_label.setText(f"프로젝트: {proj['name']}")
            self._status_bar.showMessage(f"프로젝트 '{proj['name']}' 선택됨", 3000)
        self._sidebar.refresh_conversations(project_id)

    def _on_project_cleared(self):
        self._current_project_id = None
        self._project_label.setText("")
        self._sidebar.refresh_conversations(None)

    def _on_new_project(self):
        from gui.project_dialog import ProjectDialog
        dialog = ProjectDialog(self._db, parent=self)
        if dialog.exec() == 1:
            self._sidebar.refresh_projects()
            if dialog.project_id:
                self._on_project_selected(dialog.project_id)

    def _on_edit_project(self, project_id: int):
        from gui.project_dialog import ProjectDialog
        dialog = ProjectDialog(self._db, project_id=project_id, parent=self)
        result = dialog.exec()
        if result == 2:
            self._on_project_cleared()
        self._sidebar.refresh_projects()

    # === Mode / Settings ===

    def _on_mode_changed(self, idx: int):
        self._mode = self._mode_combo.itemData(idx)
        self._status_bar.showMessage(f"모드 변경: {self._mode_combo.currentText()}", 3000)

    def _on_settings(self):
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._engine, self)
        if dialog.exec():
            self._update_engine_status()
            self._status_bar.showMessage("설정이 저장되었습니다.", 3000)

    # === Status ===

    def _update_engine_status(self):
        self._engine_label.setText(f"엔진: {self._engine.get_current_engine_name()}")
        self._usage_label.setText(f"사용량: {self._engine.get_usage_text()}")

    def _start_status_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_resource_status)
        self._timer.start(5000)

    def _update_resource_status(self):
        ram = psutil.virtual_memory()
        self._ram_label.setText(f"RAM: {ram.used / (1024**3):.1f}/{ram.total / (1024**3):.1f}GB")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        if self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.cancel()
            self._agent_worker.wait(3000)
        self._db.close()
        super().closeEvent(event)
