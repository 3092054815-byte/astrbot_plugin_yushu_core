"""Manual owner-only memory storage for yushu_core.

The store only creates SQLite files when an explicit write command is used.
Read commands return empty/not-found results when the database does not exist.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLUGIN_DATA_DIR = Path("/root/astrbot/data/plugin_data/astrbot_plugin_yushu_core")
CONTAINER_PLUGIN_DATA_DIR = Path(
    "/AstrBot/data/plugin_data/astrbot_plugin_yushu_core"
)

ALLOWED_MEMORY_TYPES = {
    "profile",
    "preference",
    "boundary",
    "open_thread",
    "skill_goal",
    "relationship",
    "fact",
    "group_rule",
}
LOW_VALUE_TYPES = {"open_thread"}

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_items (
  id TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  type TEXT NOT NULL,
  content TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  expires_at TEXT,
  source TEXT NOT NULL DEFAULT 'manual',
  pinned INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memory_user_scope_type
ON memory_items(user_id, scope, type);

CREATE INDEX IF NOT EXISTS idx_memory_user_created
ON memory_items(user_id, created_at);

CREATE TABLE IF NOT EXISTS memory_runtime_flags (
  user_id TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 1,
  paused_until TEXT,
  updated_at TEXT NOT NULL
);
""".strip()

SENSITIVE_KEYWORDS = (
    "token",
    "cookie",
    "password",
    "passwd",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "密钥",
    "密码",
    "身份证",
    "手机号",
    "住址",
    "银行卡",
    "验证码",
    "账号凭据",
    "完整聊天记录",
)


@dataclass(frozen=True)
class MemoryLimits:
    max_memory_per_user: int = 50
    max_pinned_memory_per_user: int = 15
    memory_db_limit_mb: int = 2
    memory_exports_limit_mb: int = 2
    memory_total_limit_mb: int = 4
    memory_export_file_limit_kb: int = 512
    memory_content_max_chars: int = 500
    memory_auto_prune_enabled: bool = False

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "MemoryLimits":
        data = config or {}
        return cls(
            max_memory_per_user=_positive_int(
                data.get("max_memory_per_user"), cls.max_memory_per_user
            ),
            max_pinned_memory_per_user=_positive_int(
                data.get("max_pinned_memory_per_user"),
                cls.max_pinned_memory_per_user,
            ),
            memory_db_limit_mb=_positive_int(
                data.get("memory_db_limit_mb"), cls.memory_db_limit_mb
            ),
            memory_exports_limit_mb=_positive_int(
                data.get("memory_exports_limit_mb"), cls.memory_exports_limit_mb
            ),
            memory_total_limit_mb=_positive_int(
                data.get("memory_total_limit_mb"), cls.memory_total_limit_mb
            ),
            memory_export_file_limit_kb=_positive_int(
                data.get("memory_export_file_limit_kb"),
                cls.memory_export_file_limit_kb,
            ),
            memory_content_max_chars=_positive_int(
                data.get("memory_content_max_chars"), cls.memory_content_max_chars
            ),
            memory_auto_prune_enabled=bool(
                data.get("memory_auto_prune_enabled", False)
            ),
        )

    @property
    def db_limit_bytes(self) -> int:
        return self.memory_db_limit_mb * 1024 * 1024

    @property
    def exports_limit_bytes(self) -> int:
        return self.memory_exports_limit_mb * 1024 * 1024

    @property
    def total_limit_bytes(self) -> int:
        return self.memory_total_limit_mb * 1024 * 1024

    @property
    def export_file_limit_bytes(self) -> int:
        return self.memory_export_file_limit_kb * 1024


class MemoryStoreError(ValueError):
    """Structured user-facing memory store failure."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _short_content(content: object) -> str:
    text = str(content or "")
    if contains_sensitive_field(text):
        return "<hidden>"
    return text[:40]


def contains_sensitive_field(text: object) -> bool:
    """Return whether text appears to contain data that should not be stored."""

    lowered = str(text or "").lower()
    return any(keyword.lower() in lowered for keyword in SENSITIVE_KEYWORDS)


def should_reject_memory(
    content: object,
    limits: MemoryLimits | None = None,
) -> tuple[bool, str]:
    """Return a conservative reject decision for memory content."""

    text = str(content or "").strip()
    active_limits = limits or MemoryLimits()
    if not text:
        return True, "empty_content"
    if contains_sensitive_field(text):
        return True, "sensitive_content"
    if len(text) > active_limits.memory_content_max_chars:
        return True, "content_too_long"
    return False, "ok"


def default_data_dir() -> Path:
    """Return the plugin data dir for host or container execution."""

    if Path("/AstrBot/data").exists():
        return CONTAINER_PLUGIN_DATA_DIR
    return PLUGIN_DATA_DIR


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


class MemoryStore:
    """SQLite-backed manual memory store."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        exports_dir: Path | str | None = None,
        limits: MemoryLimits | None = None,
    ) -> None:
        data_dir = default_data_dir()
        self.db_path = Path(db_path) if db_path else data_dir / "yushu_memory.sqlite3"
        self.exports_dir = Path(exports_dir) if exports_dir else data_dir / "exports"
        self.limits = limits or MemoryLimits()

    @property
    def data_dir(self) -> Path:
        return self.db_path.parent

    def _connect(self, create: bool) -> sqlite3.Connection | None:
        if not create and not self.db_path.exists():
            return None
        if create:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        if create:
            conn.executescript(SQLITE_SCHEMA)
            conn.commit()
        return conn

    def _db_size(self) -> int:
        return self.db_path.stat().st_size if self.db_path.exists() else 0

    def _exports_size(self) -> int:
        return directory_size(self.exports_dir)

    def _total_size(self) -> int:
        return directory_size(self.data_dir)

    def _ensure_write_capacity(self) -> None:
        if self._db_size() > self.limits.db_limit_bytes:
            raise MemoryStoreError("db_limit_exceeded")
        if self._exports_size() > self.limits.exports_limit_bytes:
            raise MemoryStoreError("exports_limit_exceeded")
        if self._total_size() > self.limits.total_limit_bytes:
            raise MemoryStoreError("total_limit_exceeded")

    def status(self, user_id: str, scope: str) -> dict[str, Any]:
        return {
            "db_exists": self.db_path.exists(),
            "memory_count": self.count_memories(user_id, scope),
            "pinned_count": self.count_pinned(user_id, scope),
            "db_size_bytes": self._db_size(),
            "exports_size_bytes": self._exports_size(),
            "total_size_bytes": self._total_size(),
            "db_limit_bytes": self.limits.db_limit_bytes,
            "exports_limit_bytes": self.limits.exports_limit_bytes,
            "total_limit_bytes": self.limits.total_limit_bytes,
        }

    def count_memories(
        self,
        user_id: str,
        scope: str,
        memory_type: str | None = None,
    ) -> int:
        conn = self._connect(create=False)
        if conn is None:
            return 0
        try:
            if memory_type:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM memory_items
                    WHERE user_id = ? AND scope = ? AND type = ?
                    """,
                    (user_id, scope, memory_type),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM memory_items
                    WHERE user_id = ? AND scope = ?
                    """,
                    (user_id, scope),
                ).fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()

    def count_pinned(self, user_id: str, scope: str) -> int:
        conn = self._connect(create=False)
        if conn is None:
            return 0
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count FROM memory_items
                WHERE user_id = ? AND scope = ? AND pinned = 1
                """,
                (user_id, scope),
            ).fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()

    def list_scopes(self, user_id: str) -> list[str]:
        """Return distinct memory scopes for a user without exposing session ids."""

        conn = self._connect(create=False)
        if conn is None:
            return []
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT scope FROM memory_items
                WHERE user_id = ?
                ORDER BY CASE WHEN scope = 'private' THEN 0 ELSE 1 END, scope
                """,
                (user_id,),
            ).fetchall()
            return [str(row["scope"] or "") for row in rows if str(row["scope"] or "")]
        finally:
            conn.close()

    def list_memories(
        self,
        user_id: str,
        scope: str,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        conn = self._connect(create=False)
        if conn is None:
            return []
        try:
            if memory_type:
                rows = conn.execute(
                    """
                    SELECT * FROM memory_items
                    WHERE user_id = ? AND scope = ? AND type = ?
                    ORDER BY pinned DESC, created_at DESC
                    """,
                    (user_id, scope, memory_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM memory_items
                    WHERE user_id = ? AND scope = ?
                    ORDER BY pinned DESC, created_at DESC
                    """,
                    (user_id, scope),
                ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                item["short_content"] = _short_content(item.get("content"))
                items.append(item)
            return items
        finally:
            conn.close()

    def get_memory(self, user_id: str, scope: str, memory_id: str) -> dict[str, Any]:
        conn = self._connect(create=False)
        if conn is None:
            raise MemoryStoreError("memory_not_found")
        try:
            item = _row_to_dict(
                conn.execute(
                    """
                    SELECT * FROM memory_items
                    WHERE id = ? AND user_id = ? AND scope = ?
                    """,
                    (memory_id, user_id, scope),
                ).fetchone()
            )
            if item is None:
                raise MemoryStoreError("memory_not_found")
            if contains_sensitive_field(item.get("content")):
                item["content"] = "<hidden>"
            return item
        finally:
            conn.close()

    def add_memory(
        self,
        user_id: str,
        scope: str,
        session_id: str,
        memory_type: str,
        content: str,
        source: str = "manual",
    ) -> dict[str, Any]:
        memory_type = str(memory_type or "").strip()
        content = str(content or "").strip()
        if memory_type not in ALLOWED_MEMORY_TYPES:
            raise MemoryStoreError("invalid_memory_type")
        rejected, reason = should_reject_memory(content, self.limits)
        if rejected:
            raise MemoryStoreError(reason)
        if self.count_memories(user_id, scope) >= self.limits.max_memory_per_user:
            raise MemoryStoreError("memory_limit_exceeded")
        self._ensure_write_capacity()

        now = _now_iso()
        memory_id = uuid.uuid4().hex[:12]
        conn = self._connect(create=True)
        assert conn is not None
        try:
            conn.execute(
                """
                INSERT INTO memory_items (
                  id, scope, session_id, user_id, type, content, confidence,
                  created_at, updated_at, expires_at, source, pinned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    scope,
                    session_id,
                    user_id,
                    memory_type,
                    content,
                    1.0,
                    now,
                    now,
                    None,
                    source,
                    0,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_memory(user_id, scope, memory_id)

    def edit_memory(
        self,
        user_id: str,
        scope: str,
        memory_id: str,
        content: str,
    ) -> dict[str, Any]:
        content = str(content or "").strip()
        rejected, reason = should_reject_memory(content, self.limits)
        if rejected:
            raise MemoryStoreError(reason)
        conn = self._connect(create=False)
        if conn is None:
            raise MemoryStoreError("memory_not_found")
        try:
            now = _now_iso()
            cur = conn.execute(
                """
                UPDATE memory_items
                SET content = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND scope = ?
                """,
                (content, now, memory_id, user_id, scope),
            )
            if cur.rowcount == 0:
                raise MemoryStoreError("memory_not_found")
            conn.commit()
        finally:
            conn.close()
        return self.get_memory(user_id, scope, memory_id)

    def update_memory_fields(
        self,
        user_id: str,
        scope: str,
        memory_id: str,
        memory_type: str,
        content: str,
    ) -> dict[str, Any]:
        memory_type = str(memory_type or "").strip()
        content = str(content or "").strip()
        if memory_type not in ALLOWED_MEMORY_TYPES:
            raise MemoryStoreError("invalid_memory_type")
        rejected, reason = should_reject_memory(content, self.limits)
        if rejected:
            raise MemoryStoreError(reason)
        conn = self._connect(create=False)
        if conn is None:
            raise MemoryStoreError("memory_not_found")
        try:
            now = _now_iso()
            cur = conn.execute(
                """
                UPDATE memory_items
                SET type = ?, content = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND scope = ?
                """,
                (memory_type, content, now, memory_id, user_id, scope),
            )
            if cur.rowcount == 0:
                raise MemoryStoreError("memory_not_found")
            conn.commit()
        finally:
            conn.close()
        return self.get_memory(user_id, scope, memory_id)

    def delete_memory(self, user_id: str, scope: str, memory_id: str) -> bool:
        conn = self._connect(create=False)
        if conn is None:
            raise MemoryStoreError("memory_not_found")
        try:
            cur = conn.execute(
                "DELETE FROM memory_items WHERE id = ? AND user_id = ? AND scope = ?",
                (memory_id, user_id, scope),
            )
            if cur.rowcount == 0:
                raise MemoryStoreError("memory_not_found")
            conn.commit()
            return True
        finally:
            conn.close()

    def clear_private(self, user_id: str) -> int:
        conn = self._connect(create=False)
        if conn is None:
            return 0
        try:
            cur = conn.execute(
                "DELETE FROM memory_items WHERE user_id = ? AND scope = ?",
                (user_id, "private"),
            )
            conn.commit()
            return int(cur.rowcount)
        finally:
            conn.close()

    def set_pinned(
        self,
        user_id: str,
        scope: str,
        memory_id: str,
        pinned: bool,
    ) -> dict[str, Any]:
        if pinned and self.count_pinned(user_id, scope) >= (
            self.limits.max_pinned_memory_per_user
        ):
            current = self.get_memory(user_id, scope, memory_id)
            if int(current.get("pinned") or 0) != 1:
                raise MemoryStoreError("pinned_limit_exceeded")

        conn = self._connect(create=False)
        if conn is None:
            raise MemoryStoreError("memory_not_found")
        try:
            cur = conn.execute(
                """
                UPDATE memory_items
                SET pinned = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND scope = ?
                """,
                (1 if pinned else 0, _now_iso(), memory_id, user_id, scope),
            )
            if cur.rowcount == 0:
                raise MemoryStoreError("memory_not_found")
            conn.commit()
        finally:
            conn.close()
        return self.get_memory(user_id, scope, memory_id)

    def set_runtime_flag(
        self,
        user_id: str,
        enabled: bool,
        paused_until: str | None = None,
    ) -> None:
        conn = self._connect(create=True)
        assert conn is not None
        try:
            conn.execute(
                """
                INSERT INTO memory_runtime_flags (
                  user_id, enabled, paused_until, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  enabled = excluded.enabled,
                  paused_until = excluded.paused_until,
                  updated_at = excluded.updated_at
                """,
                (user_id, 1 if enabled else 0, paused_until, _now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_runtime_flag(self, user_id: str) -> dict[str, Any]:
        conn = self._connect(create=False)
        if conn is None:
            return {"enabled": True, "paused_until": None}
        try:
            row = conn.execute(
                "SELECT enabled, paused_until FROM memory_runtime_flags WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return {"enabled": True, "paused_until": None}
            return {"enabled": bool(row["enabled"]), "paused_until": row["paused_until"]}
        finally:
            conn.close()

    def export_memories(
        self,
        user_id: str,
        scope: str,
        export_format: str = "md",
    ) -> dict[str, Any]:
        export_format = (export_format or "md").lower()
        if export_format not in {"jsonl", "md"}:
            raise MemoryStoreError("invalid_export_format")
        items = self.list_memories(user_id, scope)
        safe_items = [
            item for item in items if not contains_sensitive_field(item.get("content"))
        ]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "jsonl" if export_format == "jsonl" else "md"
        if export_format == "jsonl":
            body = "\n".join(
                json.dumps(_export_payload(item), ensure_ascii=False)
                for item in safe_items
            )
            if body:
                body += "\n"
        else:
            body = _markdown_export(safe_items)

        encoded = body.encode("utf-8")
        if len(encoded) > self.limits.export_file_limit_bytes:
            raise MemoryStoreError("export_file_limit_exceeded")
        if self._exports_size() + len(encoded) > self.limits.exports_limit_bytes:
            raise MemoryStoreError("exports_limit_exceeded")
        if self._total_size() + len(encoded) > self.limits.total_limit_bytes:
            raise MemoryStoreError("total_limit_exceeded")

        self.exports_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.exports_dir / f"yushu_memory_export_{timestamp}.{suffix}"
        out_path.write_text(body, encoding="utf-8")
        return {
            "path": str(out_path),
            "format": export_format,
            "exported_count": len(safe_items),
            "skipped_sensitive_count": len(items) - len(safe_items),
            "size_bytes": len(encoded),
        }

    def prune(self, user_id: str, scope: str, confirm: bool) -> dict[str, Any]:
        memory_ids = self._prunable_memory_ids(user_id, scope)
        export_files = self._old_export_files()
        planned_bytes = sum(
            path.stat().st_size for path in export_files if path.exists()
        )

        result = {
            "deleted_memories": len(memory_ids) if confirm else 0,
            "planned_memories": len(memory_ids),
            "deleted_export_files": len(export_files) if confirm else 0,
            "planned_export_files": len(export_files),
            "planned_bytes": planned_bytes,
        }
        if not confirm:
            return result

        conn = self._connect(create=False)
        if conn is not None:
            try:
                conn.executemany(
                    "DELETE FROM memory_items WHERE id = ? AND user_id = ? AND scope = ?",
                    [(memory_id, user_id, scope) for memory_id in memory_ids],
                )
                conn.commit()
            finally:
                conn.close()
        for path in export_files:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        return result

    def _prunable_memory_ids(self, user_id: str, scope: str) -> list[str]:
        conn = self._connect(create=False)
        if conn is None:
            return []
        try:
            rows = conn.execute(
                """
                SELECT id FROM memory_items
                WHERE user_id = ? AND scope = ? AND pinned = 0
                AND (
                  (expires_at IS NOT NULL AND expires_at < ?)
                  OR type IN ({})
                )
                """.format(",".join("?" for _ in LOW_VALUE_TYPES)),
                (user_id, scope, _now_iso(), *sorted(LOW_VALUE_TYPES)),
            ).fetchall()
            return [str(row["id"]) for row in rows]
        finally:
            conn.close()

    def _old_export_files(self) -> list[Path]:
        if not self.exports_dir.exists():
            return []
        files = sorted(
            [path for path in self.exports_dir.iterdir() if path.is_file()],
            key=lambda path: path.stat().st_mtime,
        )
        if self._exports_size() <= self.limits.exports_limit_bytes:
            return []
        selected: list[Path] = []
        size = self._exports_size()
        for path in files:
            selected.append(path)
            size -= path.stat().st_size
            if size <= self.limits.exports_limit_bytes:
                break
        return selected


def _export_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "owner": "current_owner",
        "scope": item.get("scope"),
        "type": item.get("type"),
        "content": item.get("content"),
        "confidence": item.get("confidence"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "expires_at": item.get("expires_at"),
        "source": item.get("source"),
        "pinned": item.get("pinned"),
    }


def _markdown_export(items: list[dict[str, Any]]) -> str:
    lines = [
        "# Yushu Memory Export",
        "",
        f"Generated at: {_now_iso()}",
        "Owner: current_owner",
        "",
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("type") or "unknown"), []).append(item)
    for memory_type in sorted(grouped):
        lines.extend([f"## {memory_type}", ""])
        for item in grouped[memory_type]:
            lines.append(f"- [{item.get('id')}] {item.get('content')}")
        lines.append("")
    return "\n".join(lines)
