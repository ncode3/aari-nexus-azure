from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MEMORY_TYPES = {
    "people",
    "organizations",
    "projects",
    "decisions",
    "tasks",
    "deadlines",
    "drafts",
    "action_packages",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    type: str
    content: str
    tags: list[str]
    created_at: str


class MemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS action_packages (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    command TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    package_json TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_status ON action_packages(status)")

    def save_memory(self, content: str, memory_type: str = "decisions", tags: list[str] | None = None) -> MemoryRecord:
        normalized_type = memory_type if memory_type in MEMORY_TYPES else "decisions"
        record = MemoryRecord(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            type=normalized_type,
            content=content.strip(),
            tags=tags or [],
            created_at=utc_now(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories (id, type, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
                (record.id, record.type, record.content, json.dumps(record.tags), record.created_at),
            )
        return record

    def search_memory(self, query: str, limit: int = 8) -> list[MemoryRecord]:
        cleaned = query.strip()
        if not cleaned:
            return self.list_recent_memory(limit=limit)
        terms = [part for part in cleaned.split() if len(part) > 1][:6]
        if not terms:
            terms = [cleaned]
        where = " OR ".join(["content LIKE ? OR tags LIKE ?" for _ in terms])
        params: list[str] = []
        for term in terms:
            pattern = f"%{term}%"
            params.extend([pattern, pattern])
        params.append(str(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, type, content, tags, created_at
                FROM memories
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def list_recent_memory(self, limit: int = 8) -> list[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, type, content, tags, created_at
                FROM memories
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def save_action_package(self, package: dict[str, Any]) -> dict[str, Any]:
        package_id = str(package.get("id") or f"act_{uuid.uuid4().hex[:12]}")
        created_at = str(package.get("created_at") or utc_now())
        status = str(package.get("status") or "pending")
        stored = {**package, "id": package_id, "created_at": created_at, "status": status}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO action_packages
                    (id, created_at, command, agent, intent, package_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    package_id,
                    created_at,
                    str(stored.get("command", "")),
                    str(stored.get("agent", "")),
                    str(stored.get("intent", "")),
                    json.dumps(stored, ensure_ascii=True, sort_keys=True),
                    status,
                ),
            )
        return stored

    def get_pending_action(self, action_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            if action_id:
                row = conn.execute(
                    "SELECT package_json FROM action_packages WHERE id = ? AND status = 'pending'",
                    (action_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT package_json FROM action_packages
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ).fetchone()
        return json.loads(row["package_json"]) if row else None

    def update_action_status(self, action_id: str, status: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT package_json FROM action_packages WHERE id = ?", (action_id,)).fetchone()
            if not row:
                return None
            package = json.loads(row["package_json"])
            package["status"] = status
            package["updated_at"] = utc_now()
            conn.execute(
                "UPDATE action_packages SET package_json = ?, status = ? WHERE id = ?",
                (json.dumps(package, ensure_ascii=True, sort_keys=True), status, action_id),
            )
        return package

    def _record_from_row(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            type=row["type"],
            content=row["content"],
            tags=json.loads(row["tags"]),
            created_at=row["created_at"],
        )


def save_memory(store: MemoryStore, content: str, memory_type: str = "decisions", tags: list[str] | None = None) -> MemoryRecord:
    return store.save_memory(content=content, memory_type=memory_type, tags=tags)


def search_memory(store: MemoryStore, query: str, limit: int = 8) -> list[MemoryRecord]:
    return store.search_memory(query=query, limit=limit)


def list_recent_memory(store: MemoryStore, limit: int = 8) -> list[MemoryRecord]:
    return store.list_recent_memory(limit=limit)


def save_action_package(store: MemoryStore, package: dict[str, Any]) -> dict[str, Any]:
    return store.save_action_package(package)


def get_pending_action(store: MemoryStore, action_id: str | None = None) -> dict[str, Any] | None:
    return store.get_pending_action(action_id)


def update_action_status(store: MemoryStore, action_id: str, status: str) -> dict[str, Any] | None:
    return store.update_action_status(action_id, status)
