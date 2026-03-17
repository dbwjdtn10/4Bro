"""SQLite database manager for conversations, projects, and bookmarks."""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional


def _get_db_path() -> str:
    db_dir = os.path.join(os.path.expanduser("~"), "Documents", "4Bro")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "4bro.db")


class Database:
    """SQLite database for 4Bro persistent storage."""

    def __init__(self, db_path: str | None = None):
        self._path = db_path or _get_db_path()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        """Create all required tables and indexes if they don't exist."""
        with self._lock:
            self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                genre TEXT DEFAULT '',
                target TEXT DEFAULT '',
                tone TEXT DEFAULT '',
                kpi TEXT DEFAULT '',
                competitors TEXT DEFAULT '',
                usp TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                title TEXT DEFAULT '',
                mode TEXT DEFAULT 'ad_expert',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                project_id INTEGER,
                content TEXT NOT NULL,
                label TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_project_id ON conversations(project_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_project_id ON bookmarks(project_id);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_conversation_id ON bookmarks(conversation_id);

            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            """)
            self._conn.commit()

    def close(self):
        """Close the database connection."""
        self._conn.close()

    # === Projects ===

    def create_project(self, name: str, **kwargs) -> int:
        """Create a new project and return its ID."""
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO projects (name, genre, target, tone, kpi, competitors, usp, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    kwargs.get("genre", ""),
                    kwargs.get("target", ""),
                    kwargs.get("tone", ""),
                    kwargs.get("kpi", ""),
                    kwargs.get("competitors", ""),
                    kwargs.get("usp", ""),
                    kwargs.get("notes", ""),
                ),
            )
            self._conn.commit()
            return cur.lastrowid or 0

    def update_project(self, project_id: int, **kwargs):
        """Update project fields by ID."""
        fields = []
        values = []
        for key in ("name", "genre", "target", "tone", "kpi", "competitors", "usp", "notes"):
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        if not fields:
            return
        fields.append("updated_at = datetime('now','localtime')")
        values.append(project_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE projects SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            self._conn.commit()

    def delete_project(self, project_id: int):
        """Delete a project by ID."""
        with self._lock:
            self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn.commit()

    def get_project(self, project_id: int) -> Optional[dict]:
        """Return a project dict by ID, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_projects(self) -> list[dict]:
        """Return all projects ordered by most recently updated."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_project_context(self, project_id: int) -> str:
        """Build a context string from project profile for system prompt injection.

        Note: calls get_project() which acquires its own lock.
        """
        proj = self.get_project(project_id)
        if not proj:
            return ""
        parts = [f"[현재 프로젝트: {proj['name']}]"]
        if proj["genre"]:
            parts.append(f"- 장르: {proj['genre']}")
        if proj["target"]:
            parts.append(f"- 타겟: {proj['target']}")
        if proj["tone"]:
            parts.append(f"- 톤앤매너: {proj['tone']}")
        if proj["kpi"]:
            parts.append(f"- 주요 KPI: {proj['kpi']}")
        if proj["competitors"]:
            parts.append(f"- 경쟁사: {proj['competitors']}")
        if proj["usp"]:
            parts.append(f"- USP: {proj['usp']}")
        if proj["notes"]:
            parts.append(f"- 메모: {proj['notes']}")
        return "\n".join(parts)

    # === Conversations ===

    def create_conversation(
        self,
        title: str = "",
        project_id: int | None = None,
        mode: str = "ad_expert",
    ) -> int:
        """Create a new conversation and return its ID."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO conversations (title, project_id, mode) VALUES (?, ?, ?)",
                (title, project_id, mode),
            )
            self._conn.commit()
            return cur.lastrowid or 0

    def update_conversation(self, conv_id: int, **kwargs):
        """Update conversation fields by ID."""
        fields = []
        values = []
        for key in ("title", "project_id", "mode"):
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        if not fields:
            return
        fields.append("updated_at = datetime('now','localtime')")
        values.append(conv_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE conversations SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            self._conn.commit()

    def delete_conversation(self, conv_id: int):
        """Delete a conversation and its messages (CASCADE)."""
        with self._lock:
            self._conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            self._conn.commit()

    def list_conversations(
        self, project_id: int | None = None, limit: int | None = None, offset: int = 0
    ) -> list[dict]:
        """List conversations, optionally filtered by project, with pagination."""
        with self._lock:
            if project_id is not None:
                sql = "SELECT * FROM conversations WHERE project_id = ? ORDER BY updated_at DESC"
                params: list = [project_id]
            else:
                sql = "SELECT * FROM conversations ORDER BY updated_at DESC"
                params = []

            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def count_conversations(self, project_id: int | None = None) -> int:
        """Return the total number of conversations, optionally filtered by project."""
        with self._lock:
            if project_id is not None:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM conversations"
                ).fetchone()
            return row[0] if row else 0

    def get_conversation(self, conv_id: int) -> Optional[dict]:
        """Return a conversation dict by ID, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            return dict(row) if row else None

    # === Messages ===

    def add_message(self, conv_id: int, role: str, content: str) -> int:
        """Add a message to a conversation and update its timestamp."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conv_id, role, content),
            )
            # Update conversation timestamp
            self._conn.execute(
                "UPDATE conversations SET updated_at = datetime('now','localtime') WHERE id = ?",
                (conv_id,),
            )
            self._conn.commit()
            return cur.lastrowid or 0

    def get_messages(
        self, conv_id: int, limit: int | None = None, offset: int = 0
    ) -> list[dict]:
        """Return messages for a conversation in chronological order."""
        with self._lock:
            if limit is not None:
                # Fetch the most recent N messages (with offset) by selecting
                # in DESC order, then reverse to return in chronological order.
                rows = self._conn.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? "
                    "ORDER BY id DESC LIMIT ? OFFSET ?",
                    (conv_id, limit, offset),
                ).fetchall()
                return [dict(r) for r in reversed(rows)]
            else:
                rows = self._conn.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                    (conv_id,),
                ).fetchall()
                return [dict(r) for r in rows]

    def count_messages(self, conversation_id: int) -> int:
        """Return the total number of messages in a conversation."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            return row[0] if row else 0

    # === Bookmarks ===

    def add_bookmark(
        self,
        content: str,
        label: str = "",
        conversation_id: int | None = None,
        project_id: int | None = None,
    ) -> int:
        """Add a bookmark and return its ID."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO bookmarks (content, label, conversation_id, project_id) VALUES (?, ?, ?, ?)",
                (content, label, conversation_id, project_id),
            )
            self._conn.commit()
            return cur.lastrowid or 0

    def update_bookmark_label(self, bookmark_id: int, label: str):
        """Update bookmark label/tag."""
        with self._lock:
            self._conn.execute(
                "UPDATE bookmarks SET label = ? WHERE id = ?",
                (label, bookmark_id),
            )
            self._conn.commit()

    def list_bookmarks(self, project_id: int | None = None) -> list[dict]:
        """List bookmarks, optionally filtered by project."""
        with self._lock:
            if project_id is not None:
                rows = self._conn.execute(
                    "SELECT * FROM bookmarks WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM bookmarks ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def delete_bookmark(self, bookmark_id: int):
        """Delete a bookmark by ID."""
        with self._lock:
            self._conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            self._conn.commit()

    # === Conversations (rename) ===

    def rename_conversation(self, conv_id: int, new_title: str):
        """Rename a conversation."""
        with self._lock:
            self._conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (new_title, conv_id),
            )
            self._conn.commit()

    # === Templates ===

    def add_template(self, name: str, content: str) -> int:
        """Add a prompt template and return its ID."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO templates (name, content) VALUES (?, ?)",
                (name, content),
            )
            self._conn.commit()
            return cur.lastrowid or 0

    def list_templates(self) -> list[dict]:
        """Return all templates ordered by name."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, content, created_at FROM templates ORDER BY name"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_template(self, template_id: int) -> dict | None:
        """Return a template dict by ID, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, content FROM templates WHERE id = ?",
                (template_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_template(self, template_id: int, name: str, content: str):
        """Update a template's name and content."""
        with self._lock:
            self._conn.execute(
                "UPDATE templates SET name = ?, content = ? WHERE id = ?",
                (name, content, template_id),
            )
            self._conn.commit()

    def delete_template(self, template_id: int):
        """Delete a template by ID."""
        with self._lock:
            self._conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            self._conn.commit()
