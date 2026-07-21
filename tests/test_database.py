import sqlite3
from pathlib import Path

from carenest.database import WishlistDatabase


def test_database_initialization_and_basic_operations(tmp_path: Path) -> None:
    database = WishlistDatabase(tmp_path / "data" / "wishlist.db")

    database.initialize()
    item_id = database.add_item("Книга")

    assert item_id == 1
    assert database.get_items() == [(1, "Книга")]


def test_existing_items_table_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "wishlist.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO items (id, name) VALUES (7, 'Старое желание')")
        connection.commit()

    database = WishlistDatabase(path)
    database.initialize()

    assert database.get_items() == [(7, "Старое желание")]
