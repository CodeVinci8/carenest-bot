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
