"""Локальное хранилище: SQLite + файлы в приватной папке приложения."""
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path


class LocalStorage:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.base_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "history.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    output_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def hash_bytes(data):
        if isinstance(data, bytearray):
            data = bytes(data)
        return hashlib.sha256(data).hexdigest()[:16]
    def save_result(self, operation, input_hash, image_arr, save_func):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{operation}_{ts}.png"
        out_path = self.output_dir / filename
        ok = save_func(image_arr, str(out_path))
        if not ok:
            return None
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO history (operation, input_hash, output_path, created_at) "
                "VALUES (?, ?, ?, ?)",
                (operation, input_hash, str(out_path), ts),
            )
        return out_path

    def get_history(self, limit=50):
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "SELECT operation, output_path, created_at "
                "FROM history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return cur.fetchall()