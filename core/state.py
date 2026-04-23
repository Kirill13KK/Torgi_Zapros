import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    triggered_by TEXT NOT NULL,
    total INTEGER,
    sent INTEGER,
    skipped INTEGER,
    errors INTEGER,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_name TEXT,
    row_index INTEGER NOT NULL,
    partner_name TEXT,
    asset_name TEXT,
    property_type TEXT,
    status TEXT NOT NULL,
    sent_at TEXT,
    error_code TEXT,
    attempt INTEGER,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS last_success (
    row_key TEXT PRIMARY KEY,
    last_success_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sends_run ON sends(run_id);
"""


def row_key(partner: str, asset: str) -> str:
    raw = f"{partner.strip().lower()}|{asset.strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class State:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init()

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)
            # migration: add source_name to sends if missing
            cols = {r["name"] for r in c.execute("PRAGMA table_info(sends)").fetchall()}
            if "source_name" not in cols:
                c.execute("ALTER TABLE sends ADD COLUMN source_name TEXT")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def create_run(self, run_id: str, mode: str, triggered_by: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO runs(run_id, mode, started_at, triggered_by) VALUES (?, ?, ?, ?)",
                (run_id, mode, utcnow_iso(), triggered_by),
            )

    def finish_run(self, run_id: str, total: int, sent: int, skipped: int, errors: int, summary: dict) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE runs SET finished_at=?, total=?, sent=?, skipped=?, errors=?, summary_json=? WHERE run_id=?",
                (utcnow_iso(), total, sent, skipped, errors, json.dumps(summary, ensure_ascii=False), run_id),
            )

    def log_send(self, run_id: str, source_name: str, row_index: int, partner: str, asset: str,
                 ptype: str | None, status: str, error_code: str | None, attempt: int) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO sends(run_id,source_name,row_index,partner_name,asset_name,property_type,status,sent_at,error_code,attempt) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, source_name, row_index, partner, asset, ptype, status,
                 utcnow_iso() if status == "SENT" else None, error_code, attempt),
            )

    def _get_last(self, key_hash: str) -> datetime | None:
        with self._conn() as c:
            cur = c.execute("SELECT last_success_at FROM last_success WHERE row_key=?", (key_hash,))
            r = cur.fetchone()
        return datetime.fromisoformat(r["last_success_at"]) if r else None

    def mark_success(self, partner: str, key: str) -> None:
        k = row_key(partner, key)
        with self._conn() as c:
            c.execute(
                "INSERT INTO last_success(row_key,last_success_at) VALUES(?,?) "
                "ON CONFLICT(row_key) DO UPDATE SET last_success_at=excluded.last_success_at",
                (k, utcnow_iso()),
            )

    def last_run(self) -> dict | None:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1")
            r = cur.fetchone()
        return dict(r) if r else None

    def is_within_window(self, partner: str, key: str, hours: int,
                         legacy_keys: list[str] | None = None) -> bool:
        candidates = [key] + (legacy_keys or [])
        for cand in candidates:
            last = self._get_last(row_key(partner, cand))
            if last is not None and datetime.now(timezone.utc) - last < timedelta(hours=hours):
                return True
        return False

    def clear_row_window(self, partner: str, source_name: str, row_index: int) -> int:
        keys: set[str] = set()
        for ptype in ("realty", "vehicle", "weapon"):
            keys.add(row_key(partner, f"{source_name}:r{row_index}:{ptype}"))
            keys.add(row_key(partner, f"r{row_index}:{ptype}"))
        with self._conn() as c:
            sent = c.execute(
                "SELECT DISTINCT asset_name FROM sends "
                "WHERE row_index=? AND source_name=? AND partner_name=? AND status='SENT'",
                (row_index, source_name, partner),
            ).fetchall()
            for r in sent:
                asset = (r["asset_name"] or "").strip()
                if asset:
                    keys.add(row_key(partner, asset))
            deleted = 0
            for k in keys:
                deleted += c.execute("DELETE FROM last_success WHERE row_key=?", (k,)).rowcount
        return deleted

    def clear_partner_window(self, partner_substr: str) -> tuple[int, list[str]]:
        """Clear window for any partner whose name contains partner_substr (case-insensitive).
        Returns (deleted_count, list of matched partner names)."""
        low = partner_substr.strip().lower()
        with self._conn() as c:
            all_sent = c.execute(
                "SELECT DISTINCT partner_name, asset_name, row_index, property_type, source_name "
                "FROM sends WHERE status='SENT'"
            ).fetchall()
            matched = [r for r in all_sent if low in (r["partner_name"] or "").strip().lower()]
            partners = sorted({r["partner_name"] for r in matched if r["partner_name"]})
            keys: set[str] = set()
            for r in matched:
                partner = (r["partner_name"] or "").strip()
                asset = (r["asset_name"] or "").strip()
                rid = r["row_index"]
                pt = r["property_type"] or ""
                src = r["source_name"] or ""
                if asset:
                    keys.add(row_key(partner, asset))
                if pt:
                    keys.add(row_key(partner, f"r{rid}:{pt}"))
                    if src:
                        keys.add(row_key(partner, f"{src}:r{rid}:{pt}"))
            deleted = 0
            for k in keys:
                deleted += c.execute("DELETE FROM last_success WHERE row_key=?", (k,)).rowcount
        return deleted, partners
