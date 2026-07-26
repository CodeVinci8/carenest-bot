from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, datetime
from pathlib import Path


class WishlistDatabase:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS compliment_history (
                    id INTEGER PRIMARY KEY,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    delivered_at TEXT,
                    delivery_state TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS media_shuffle (
                    category TEXT PRIMARY KEY,
                    remaining_json TEXT NOT NULL,
                    last_item TEXT
                )
                """
            )
            connection.commit()

    def add_item(self, name: str) -> int:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute("INSERT INTO items (name) VALUES (?)", (name,))
            connection.commit()
            return int(cursor.lastrowid)

    def get_items(self) -> list[tuple[int, str]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT id, name FROM items ORDER BY id").fetchall()
        return [(int(item_id), str(name)) for item_id, name in rows]

    def get_item(self, item_id: int) -> tuple[int, str] | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT id, name FROM items WHERE id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return int(row[0]), str(row[1])

    def delete_item(self, item_id: int, expected_name: str) -> bool:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "DELETE FROM items WHERE id = ? AND name = ?",
                (item_id, expected_name),
            )
            connection.commit()
            return cursor.rowcount == 1

    def get_state(self, key: str) -> str | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key = ?",
                (key,),
            ).fetchone()
        return None if row is None else str(row[0])

    def set_state(self, key: str, value: str) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO app_state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            connection.commit()

    def ensure_compliment_baseline(self, local_date: date) -> date:
        stored = self.get_state("compliments_baseline_date")
        if stored:
            return date.fromisoformat(stored)
        self.set_state("compliments_baseline_date", local_date.isoformat())
        return local_date

    def last_compliment_date(self) -> date | None:
        stored = self.get_state("compliments_last_success_date")
        return date.fromisoformat(stored) if stored else None

    def create_compliment(
        self,
        text: str,
        source: str,
        generated_at: datetime,
    ) -> int:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO compliment_history
                    (text, source, generated_at, delivery_state)
                VALUES (?, ?, ?, 'pending')
                """,
                (text, source, generated_at.isoformat()),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def mark_compliment_failed(self, compliment_id: int) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE compliment_history
                SET delivery_state = 'failed'
                WHERE id = ? AND delivery_state = 'pending'
                """,
                (compliment_id,),
            )
            connection.commit()

    def mark_compliment_delivered(
        self,
        compliment_id: int,
        delivered_at: datetime,
        local_date: date,
    ) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE compliment_history
                SET delivery_state = 'sent', delivered_at = ?
                WHERE id = ? AND delivery_state = 'pending'
                """,
                (delivered_at.isoformat(), compliment_id),
            )
            connection.execute(
                """
                INSERT INTO app_state (key, value)
                VALUES ('compliments_last_success_date', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (local_date.isoformat(),),
            )
            connection.commit()

    def recent_compliments(self, limit: int = 10) -> list[str]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT text FROM compliment_history
                WHERE delivery_state = 'sent'
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def next_media_name(
        self,
        category: str,
        available: list[str],
        *,
        randomizer: random.Random | None = None,
    ) -> str | None:
        names = sorted(set(available))
        if not names:
            return None
        chooser = randomizer or random
        with sqlite3.connect(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT remaining_json, last_item FROM media_shuffle WHERE category = ?",
                (category,),
            ).fetchone()
            last_item = str(row[1]) if row and row[1] is not None else None
            remaining: list[str] = []
            if row:
                try:
                    stored = json.loads(str(row[0]))
                    if isinstance(stored, list):
                        remaining = [name for name in stored if name in names]
                except json.JSONDecodeError:
                    remaining = []
            if not remaining:
                remaining = [name for name in names if len(names) == 1 or name != last_item]
                chooser.shuffle(remaining)
            selected = remaining.pop(0)
            connection.execute(
                """
                INSERT INTO media_shuffle (category, remaining_json, last_item)
                VALUES (?, ?, ?)
                ON CONFLICT(category) DO UPDATE SET
                    remaining_json = excluded.remaining_json,
                    last_item = excluded.last_item
                """,
                (category, json.dumps(remaining), selected),
            )
            connection.commit()
        return selected
