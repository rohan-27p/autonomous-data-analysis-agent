from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from autodata_agent.core.schemas import AnalysisResponse, SessionRecord


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create_session_id(self) -> str:
        return uuid.uuid4().hex

    def append(
        self,
        session_id: str,
        dataset_id: str,
        question: str,
        response: AnalysisResponse,
    ) -> str:
        record_id = uuid.uuid4().hex
        payload = response.model_dump_json()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO session_records(
                    record_id,
                    session_id,
                    dataset_id,
                    question,
                    response_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (record_id, session_id, dataset_id, question, payload),
            )
        return record_id

    def history(self, session_id: str, *, limit: int = 20) -> list[SessionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT record_id, session_id, dataset_id, question, response_json, created_at
                FROM session_records
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        records: list[SessionRecord] = []
        for record_id, sid, dataset_id, question, response_json, created_at in reversed(rows):
            records.append(
                SessionRecord(
                    record_id=record_id,
                    session_id=sid,
                    dataset_id=dataset_id,
                    question=question,
                    response=AnalysisResponse.model_validate(json.loads(response_json)),
                    created_at=created_at,
                )
            )
        return records

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_records(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_records_session
                ON session_records(session_id)
                """
            )
