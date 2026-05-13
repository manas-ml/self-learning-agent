from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLExecutor:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row

    def execute(self, query: str) -> tuple[list[dict] | None, str | None]:
        try:
            cur = self._conn.cursor()
            cur.execute(query)
            self._conn.commit()
            rows = [dict(r) for r in (cur.fetchall() or [])]
            return rows, None
        except sqlite3.Error as e:
            return None, str(e)

    def setup_sample_db(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            price       REAL NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            stock       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS customers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER REFERENCES customers(id),
            product_id  INTEGER REFERENCES products(id),
            quantity    INTEGER NOT NULL,
            total       REAL NOT NULL,
            order_date  TEXT DEFAULT (date('now'))
        );
        """
        seed = """
        INSERT OR IGNORE INTO categories(name) VALUES ('Electronics'),('Clothing'),('Books');
        INSERT OR IGNORE INTO products(name, price, category_id, stock)
            VALUES ('Laptop', 999.99, 1, 50),
                   ('T-Shirt', 19.99, 2, 200),
                   ('Python Book', 49.99, 3, 100),
                   ('Headphones', 149.99, 1, 75);
        INSERT OR IGNORE INTO customers(name, email)
            VALUES ('Alice', 'alice@example.com'),
                   ('Bob', 'bob@example.com'),
                   ('Carol', 'carol@example.com');
        INSERT OR IGNORE INTO orders(customer_id, product_id, quantity, total)
            VALUES (1, 1, 1, 999.99),
                   (2, 3, 2, 99.98),
                   (1, 4, 1, 149.99),
                   (3, 2, 3, 59.97);
        """
        cur = self._conn.cursor()
        cur.executescript(ddl + seed)
        self._conn.commit()

    def get_schema(self) -> str:
        cur = self._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        parts = []
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            cols = ", ".join(f"{r[1]} {r[2]}" for r in cur.fetchall())
            parts.append(f"{table}({cols})")
        return "\n".join(parts)

    def close(self) -> None:
        self._conn.close()
