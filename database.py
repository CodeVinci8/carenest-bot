import sqlite3


DB_NAME = "wishlist.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_item(name: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO items (name) VALUES (?)",
        (name,)
    )

    conn.commit()
    conn.close()


def get_items():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM items")
    items = cursor.fetchall()

    conn.close()
    return items