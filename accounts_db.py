import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "mailjet_accounts.db"


class AccountsDB:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.initialize()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL UNIQUE,
                    api_key    TEXT NOT NULL,
                    api_secret TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

    def add_account(self, name: str, api_key: str, api_secret: str) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO accounts (name, api_key, api_secret) VALUES (?, ?, ?)",
                (name, api_key, api_secret),
            )
            return cursor.lastrowid

    def delete_account(self, account_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            return cursor.rowcount == 1

    def get_all_accounts(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, api_key, api_secret, created_at FROM accounts ORDER BY name ASC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_account_by_id(self, account_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, name, api_key, api_secret, created_at FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_account(self, account_id: int, name: str, api_key: str, api_secret: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE accounts SET name = ?, api_key = ?, api_secret = ? WHERE id = ?",
                (name, api_key, api_secret, account_id),
            )
            return cursor.rowcount == 1

    def account_name_exists(self, name: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM accounts WHERE name = ?", (name,)
            ).fetchone()
            return row is not None
