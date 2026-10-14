import json
import sqlite3
from pathlib import Path

from .domain import Snapshot


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, observed_at TEXT, source TEXT, game_id TEXT, payload TEXT)")

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self, snapshot: Snapshot):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO snapshots VALUES (?, ?, ?, ?, ?)",
                       (snapshot.id, snapshot.observed_at, snapshot.source, snapshot.game_id, snapshot.model_dump_json()))

    def recent(self, limit: int = 80):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM snapshots ORDER BY rowid DESC LIMIT ?", (limit,))]

    def get(self, snapshot_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        return Snapshot.model_validate_json(row[0]) if row else None
