"""Left sidebar: projects, conversation history, recent files."""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFrame, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.database import Database


class Sidebar(QWidget):
    """Left sidebar with projects, conversations, and recent files."""

    new_chat_requested = pyqtSignal()
    conversation_selected = pyqtSignal(int)  # conversation DB id
    conversation_deleted = pyqtSignal(int)   # deleted conversation DB id
    project_selected = pyqtSignal(int)       # project DB id
    project_cleared = pyqtSignal()           # no project selected
    edit_project_requested = pyqtSignal(int)  # project DB id
    new_project_requested = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._current_project_filter: int | None = None
        self._conv_offset = 0
        self._conv_limit = 50
        self._has_more_convs = False
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self._init_ui()
        self.refresh_projects()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # App title
        title = QLabel("4Bro")
        title.setObjectName("sidebar_title")
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #89b4fa; padding: 4px 0;"
        )
        layout.addWidget(title)

        # New chat button
        self._new_chat_btn = QPushButton("+ 새 대화")
        self._new_chat_btn.setObjectName("new_chat_btn")
        self._new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self._new_chat_btn)

        # --- Projects section ---
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #45475a;")
        layout.addWidget(sep1)

        proj_header = QHBoxLayout()
        proj_label = QLabel("프로젝트")
        proj_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #a6adc8;")
        proj_header.addWidget(proj_label)
        proj_header.addStretch()

        add_proj_btn = QPushButton("+")
        add_proj_btn.setObjectName("cancel_btn")
        add_proj_btn.setFixedSize(22, 22)
        add_proj_btn.setToolTip("새 프로젝트")
        add_proj_btn.clicked.connect(self.new_project_requested.emit)
        proj_header.addWidget(add_proj_btn)
        layout.addLayout(proj_header)

        self._project_list = QListWidget()
        self._project_list.setObjectName("project_list")
        self._project_list.setMaximumHeight(120)
        self._project_list.itemClicked.connect(self._on_project_clicked)
        self._project_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._project_list.customContextMenuRequested.connect(self._on_project_context_menu)
        layout.addWidget(self._project_list)

        # --- Conversations section ---
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #45475a;")
        layout.addWidget(sep2)

        conv_label = QLabel("대화 목록")
        conv_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #a6adc8;")
        layout.addWidget(conv_label)

        self._conv_list = QListWidget()
        self._conv_list.setObjectName("conv_list")
        self._conv_list.itemClicked.connect(self._on_conv_clicked)
        self._conv_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._conv_list.customContextMenuRequested.connect(self._on_conv_context_menu)
        layout.addWidget(self._conv_list, 1)

        # "Load more" button for conversation pagination
        self._load_more_btn = QPushButton("더 보기")
        self._load_more_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #313244; color: #cdd6f4; border: 1px solid #45475a;"
            "  border-radius: 4px; padding: 4px 8px; font-size: 11px;"
            "}"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._load_more_btn.setFixedHeight(26)
        self._load_more_btn.clicked.connect(self._on_load_more_convs)
        self._load_more_btn.hide()
        layout.addWidget(self._load_more_btn)

        # --- Recent files ---
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #45475a;")
        layout.addWidget(sep3)

        recent_label = QLabel("최근 파일")
        recent_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #a6adc8;")
        layout.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.setObjectName("recent_list")
        self._recent_list.setMaximumHeight(100)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_clicked)
        layout.addWidget(self._recent_list)

    # --- Projects ---

    def refresh_projects(self):
        self._project_list.clear()
        # "All" item
        all_item = QListWidgetItem("(전체)")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self._project_list.addItem(all_item)

        for proj in self._db.list_projects():
            item = QListWidgetItem(proj["name"])
            item.setData(Qt.ItemDataRole.UserRole, proj["id"])
            item.setToolTip(f"{proj['genre']} | {proj['target']}" if proj.get("genre") else "")
            self._project_list.addItem(item)

    def _on_project_clicked(self, item: QListWidgetItem):
        proj_id = item.data(Qt.ItemDataRole.UserRole)
        if proj_id is None:
            self.project_cleared.emit()
        else:
            self.project_selected.emit(proj_id)

    def _on_project_context_menu(self, pos):
        item = self._project_list.itemAt(pos)
        if not item:
            return
        proj_id = item.data(Qt.ItemDataRole.UserRole)
        if proj_id is None:
            return

        menu = QMenu(self)
        edit_action = menu.addAction("편집")
        delete_action = menu.addAction("삭제")

        action = menu.exec(self._project_list.mapToGlobal(pos))
        if action == edit_action:
            self.edit_project_requested.emit(proj_id)
        elif action == delete_action:
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "삭제 확인",
                f"프로젝트 '{item.text()}'을(를) 삭제하시겠습니까?\n관련 대화는 유지됩니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._db.delete_project(proj_id)
                self.refresh_projects()
                self.project_cleared.emit()

    # --- Conversations (paginated) ---

    _KEEP_FILTER = object()

    def refresh_conversations(self, project_id=_KEEP_FILTER):
        """Reload conversations from scratch (resets pagination)."""
        if project_id is not Sidebar._KEEP_FILTER:
            self._current_project_filter = project_id
        self._conv_list.clear()
        self._conv_offset = 0
        self._load_conversations_page()

    def _load_conversations_page(self):
        """Load one page of conversations and append to the list."""
        convs = self._db.list_conversations(
            self._current_project_filter,
            limit=self._conv_limit,
            offset=self._conv_offset,
        )
        for conv in convs:
            title = conv["title"] or f"대화 #{conv['id']}"
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, conv["id"])
            date_str = conv.get("updated_at", "")
            if date_str:
                item.setToolTip(date_str)
            self._conv_list.addItem(item)

        self._conv_offset += len(convs)
        self._has_more_convs = len(convs) >= self._conv_limit

        if self._has_more_convs:
            self._load_more_btn.show()
        else:
            self._load_more_btn.hide()

    def _on_load_more_convs(self):
        """Load the next page of conversations."""
        self._load_conversations_page()

    def _on_conv_clicked(self, item: QListWidgetItem):
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        if conv_id is not None:
            self.conversation_selected.emit(conv_id)

    def _on_conv_context_menu(self, pos):
        item = self._conv_list.itemAt(pos)
        if not item:
            return
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        if conv_id is None:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("삭제")

        action = menu.exec(self._conv_list.mapToGlobal(pos))
        if action == delete_action:
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "삭제 확인",
                f"대화 '{item.text()}'을(를) 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._db.delete_conversation(conv_id)
                self.refresh_conversations(Sidebar._KEEP_FILTER)
                self.conversation_deleted.emit(conv_id)

    def set_active_conversation(self, conv_id: int):
        for i in range(self._conv_list.count()):
            item = self._conv_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == conv_id:
                self._conv_list.setCurrentItem(item)
                break

    # --- Recent files ---

    def add_recent_file(self, filepath: str):
        if not filepath:
            return
        name = os.path.basename(filepath)
        for i in range(self._recent_list.count()):
            if self._recent_list.item(i).data(Qt.ItemDataRole.UserRole) == filepath:
                return
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, filepath)
        item.setToolTip(filepath)
        self._recent_list.insertItem(0, item)
        while self._recent_list.count() > 10:
            self._recent_list.takeItem(self._recent_list.count() - 1)

    def _on_recent_clicked(self, item: QListWidgetItem):
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if filepath and os.path.isfile(filepath):
            import subprocess
            subprocess.Popen(["start", "", filepath], shell=True)
