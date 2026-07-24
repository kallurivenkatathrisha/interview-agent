"""
db.py
Storage layer for the Interview Agent. Uses SQLite so the whole project
runs with zero external services.

Schema
------
interviews
    id                INTEGER PRIMARY KEY
    candidate_name    TEXT
    role              TEXT
    started_at        TEXT (ISO timestamp)
    finished_at       TEXT (ISO timestamp)
    overall_score     REAL   (0-10)
    recommendation    TEXT   (Strong Hire / Hire / Unsure / No Hire)
    summary           TEXT   (agent-generated summary of the interview)

answers
    id                INTEGER PRIMARY KEY
    interview_id      INTEGER (FK -> interviews.id)
    question_id       TEXT
    question_type     TEXT   (technical / behavioral)
    question_text     TEXT
    answer_text       TEXT
    score             REAL   (0-10)
    rationale         TEXT   (why the answer got that score)
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "data" / "interviews.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL,
            role TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            overall_score REAL,
            recommendation TEXT,
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL,
            question_id TEXT NOT NULL,
            question_type TEXT,
            question_text TEXT NOT NULL,
            answer_text TEXT NOT NULL,
            score REAL,
            rationale TEXT,
            FOREIGN KEY (interview_id) REFERENCES interviews (id)
        );
        """
    )
    conn.commit()
    conn.close()


def create_interview(candidate_name: str, role: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO interviews (candidate_name, role, started_at) VALUES (?, ?, ?)",
        (candidate_name, role, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    interview_id = cur.lastrowid
    conn.close()
    return interview_id


def add_answer(interview_id: int, question: dict, answer_text: str, score: float, rationale: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO answers
           (interview_id, question_id, question_type, question_text, answer_text, score, rationale)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            interview_id,
            question["id"],
            question.get("type"),
            question["question"],
            answer_text,
            score,
            rationale,
        ),
    )
    conn.commit()
    conn.close()


def finish_interview(interview_id: int, overall_score: float, recommendation: str, summary: str):
    conn = get_connection()
    conn.execute(
        """UPDATE interviews
           SET finished_at = ?, overall_score = ?, recommendation = ?, summary = ?
           WHERE id = ?""",
        (datetime.now(timezone.utc).isoformat(), overall_score, recommendation, summary, interview_id),
    )
    conn.commit()
    conn.close()


def list_interviews(role: str = None, recommendation: str = None):
    conn = get_connection()
    query = "SELECT * FROM interviews WHERE 1=1"
    params = []
    if role:
        query += " AND role = ?"
        params.append(role)
    if recommendation:
        query += " AND recommendation = ?"
        params.append(recommendation)
    query += " ORDER BY started_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_interview(interview_id: int):
    conn = get_connection()
    interview = conn.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
    answers = conn.execute(
        "SELECT * FROM answers WHERE interview_id = ? ORDER BY id", (interview_id,)
    ).fetchall()
    conn.close()
    if not interview:
        return None
    result = dict(interview)
    result["answers"] = [dict(a) for a in answers]
    return result


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
