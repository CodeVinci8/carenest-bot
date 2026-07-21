from __future__ import annotations

import sqlite3
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
