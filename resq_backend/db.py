"""
db.py

ResQ – SQLite persistence layer.

Tables:
  rescue_events  – one row per victim per detection (full audit trail)
  rescue_status  – current status of each (drone_id, victim_id, grid) key
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "resq.db"


# ──────────────────────────────────────────────────────
# INIT
# ──────────────────────────────────────────────────────

def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS rescue_status (
                drone_id    TEXT    NOT NULL,
                victim_id   INTEGER NOT NULL,
                grid_row    INTEGER NOT NULL,
                grid_col    INTEGER NOT NULL,
                rescued     INTEGER NOT NULL DEFAULT 0,
                onway       INTEGER NOT NULL DEFAULT 0,
                rescuer     TEXT,
                last_alert  TEXT,
                updated_at  TEXT    NOT NULL,
                PRIMARY KEY (drone_id, victim_id, grid_row, grid_col)
            );

            CREATE TABLE IF NOT EXISTS rescue_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                drone_id    TEXT    NOT NULL,
                victim_id   INTEGER NOT NULL,
                priority    TEXT    NOT NULL,
                pose        TEXT,
                risk_score  REAL,
                grid_row    INTEGER,
                grid_col    INTEGER,
                mode        TEXT    DEFAULT 'rgb',
                confidence  REAL,
                detected_at TEXT    NOT NULL
            );
        """)
    print("[DB] Initialised resq.db")


# ──────────────────────────────────────────────────────
# CONNECTION HELPER
# ──────────────────────────────────────────────────────

def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


# ──────────────────────────────────────────────────────
# RESCUE STATUS — persist & restore
# ──────────────────────────────────────────────────────

def load_rescue_status() -> dict:
    """
    Load all saved rescue states into memory dict on startup.
    Returns dict keyed by (drone_id, victim_id, (grid_row, grid_col)).
    """
    result = {}
    with _conn() as con:
        rows = con.execute("SELECT * FROM rescue_status").fetchall()
    for r in rows:
        key = (r["drone_id"], r["victim_id"], (r["grid_row"], r["grid_col"]))
        result[key] = {
            "rescued":    bool(r["rescued"]),
            "onway":      bool(r["onway"]),
            "rescuer":    r["rescuer"],
            "last_alert": datetime.fromisoformat(r["last_alert"]) if r["last_alert"] else None,
        }
    print(f"[DB] Loaded {len(result)} rescue status records")
    return result


def save_rescue_status(drone_id: str, victim_id: int, grid: tuple, state: dict):
    """Upsert a single rescue status record."""
    grid_row, grid_col = grid
    last_alert = state["last_alert"].isoformat() if state.get("last_alert") else None
    with _conn() as con:
        con.execute("""
            INSERT INTO rescue_status
                (drone_id, victim_id, grid_row, grid_col, rescued, onway, rescuer, last_alert, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(drone_id, victim_id, grid_row, grid_col)
            DO UPDATE SET
                rescued    = excluded.rescued,
                onway      = excluded.onway,
                rescuer    = excluded.rescuer,
                last_alert = excluded.last_alert,
                updated_at = excluded.updated_at
        """, (
            drone_id, victim_id, grid_row, grid_col,
            int(state.get("rescued", False)),
            int(state.get("onway", False)),
            state.get("rescuer"),
            last_alert,
            datetime.utcnow().isoformat()
        ))


# ──────────────────────────────────────────────────────
# DETECTION EVENTS — log & query
# ──────────────────────────────────────────────────────

def log_detection(victim: dict, drone_id: str = "DRONE_1", mode: str = "rgb"):
    """Insert one detection event row."""
    grid = victim.get("grid", [0, 0])
    with _conn() as con:
        con.execute("""
            INSERT INTO rescue_events
                (drone_id, victim_id, priority, pose, risk_score, grid_row, grid_col, mode, confidence, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            drone_id,
            victim.get("id", 0),
            victim.get("priority", "UNKNOWN"),
            victim.get("pose", "unknown"),
            victim.get("risk_score"),
            grid[0] if len(grid) > 0 else 0,
            grid[1] if len(grid) > 1 else 0,
            mode,
            victim.get("confidence"),
            datetime.utcnow().isoformat()
        ))


def get_history(limit: int = 50) -> list:
    """Return the most recent detection events, newest first."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM rescue_events ORDER BY detected_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_mission_summary() -> dict:
    """Return aggregate stats for an export report."""
    with _conn() as con:
        total  = con.execute("SELECT COUNT(*) FROM rescue_events").fetchone()[0]
        high   = con.execute("SELECT COUNT(*) FROM rescue_events WHERE priority='HIGH'").fetchone()[0]
        medium = con.execute("SELECT COUNT(*) FROM rescue_events WHERE priority='MEDIUM'").fetchone()[0]
        low    = con.execute("SELECT COUNT(*) FROM rescue_events WHERE priority='LOW'").fetchone()[0]
        rescued = con.execute("SELECT COUNT(*) FROM rescue_status WHERE rescued=1").fetchone()[0]
        events = get_history(200)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "totals": {
            "detections": total,
            "high": high,
            "medium": medium,
            "low": low,
            "rescued": rescued,
        },
        "events": events
    }
