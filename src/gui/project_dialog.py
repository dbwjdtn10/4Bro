"""Project profile create/edit dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFormLayout, QMessageBox,
)
from PyQt6.QtCore import Qt

from core.database import Database


class ProjectDialog(QDialog):
    """Dialog for creating or editing a project profile."""

    def __init__(self, db: Database, project_id: int | None = None, parent=None):
        super().__init__(parent)
        self._db = db
        self._project_id = project_id
        self._is_edit = project_id is not None

        self.setWindowTitle("프로젝트 편집" if self._is_edit else "새 프로젝트")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._init_ui()

        if self._is_edit:
            self._load_project()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        desc = QLabel(
            "프로젝트 정보를 저장하면 대화할 때 AI가 자동으로 참고합니다."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(8)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("예: 묵혼온라인")
        form.addRow("프로젝트명 *:", self._name_input)

        self._genre_input = QLineEdit()
        self._genre_input.setPlaceholderText("예: 무협 MMORPG")
        form.addRow("장르/분야:", self._genre_input)

        self._target_input = QLineEdit()
        self._target_input.setPlaceholderText("예: 4050 남성, MMORPG 코어 유저")
        form.addRow("타겟:", self._target_input)

        self._tone_input = QLineEdit()
        self._tone_input.setPlaceholderText("예: 정통 무협, 비장함, 강호")
        form.addRow("톤앤매너:", self._tone_input)

        self._kpi_input = QLineEdit()
        self._kpi_input.setPlaceholderText("예: 사전예약 수, DAU")
        form.addRow("주요 KPI:", self._kpi_input)

        self._competitors_input = QLineEdit()
        self._competitors_input.setPlaceholderText("예: 천애명월도, 검은사막")
        form.addRow("경쟁사:", self._competitors_input)

        self._usp_input = QLineEdit()
        self._usp_input.setPlaceholderText("예: 순금 경품, 쾌속 성장")
        form.addRow("USP:", self._usp_input)

        self._notes_input = QTextEdit()
        self._notes_input.setPlaceholderText("추가 메모...")
        self._notes_input.setMaximumHeight(80)
        form.addRow("메모:", self._notes_input)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        if self._is_edit:
            delete_btn = QPushButton("삭제")
            delete_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e;")
            delete_btn.clicked.connect(self._on_delete)
            btn_row.addWidget(delete_btn)

        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _load_project(self):
        proj = self._db.get_project(self._project_id)
        if not proj:
            return
        self._name_input.setText(proj["name"])
        self._genre_input.setText(proj.get("genre", ""))
        self._target_input.setText(proj.get("target", ""))
        self._tone_input.setText(proj.get("tone", ""))
        self._kpi_input.setText(proj.get("kpi", ""))
        self._competitors_input.setText(proj.get("competitors", ""))
        self._usp_input.setText(proj.get("usp", ""))
        self._notes_input.setPlainText(proj.get("notes", ""))

    def _on_save(self):
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "알림", "프로젝트명을 입력해주세요.")
            return

        data = {
            "name": name,
            "genre": self._genre_input.text().strip(),
            "target": self._target_input.text().strip(),
            "tone": self._tone_input.text().strip(),
            "kpi": self._kpi_input.text().strip(),
            "competitors": self._competitors_input.text().strip(),
            "usp": self._usp_input.text().strip(),
            "notes": self._notes_input.toPlainText().strip(),
        }

        try:
            if self._is_edit:
                self._db.update_project(self._project_id, **data)
            else:
                self._project_id = self._db.create_project(**data)
            self.accept()
        except Exception as e:
            err_str = str(e)
            if "UNIQUE" in err_str or "unique" in err_str:
                QMessageBox.warning(self, "알림", f"'{name}' 이름은 이미 사용 중입니다.\n다른 이름을 입력해주세요.")
            else:
                QMessageBox.warning(self, "오류", f"저장 실패: {e}")

    def _on_delete(self):
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"프로젝트를 삭제하시겠습니까?\n관련 대화는 유지됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_project(self._project_id)
            self.done(2)  # special return code for delete

    @property
    def project_id(self) -> int | None:
        return self._project_id
