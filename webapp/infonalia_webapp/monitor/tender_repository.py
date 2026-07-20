from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Iterable, Mapping

from .snapshots import snapshot_completeness
from .tender_schema import SETTING_DEFAULTS, ensure_tender_monitor_schema


TERMINAL_CYCLE_STATUSES = {"completed", "completed_with_incidents", "failed"}
TERMINAL_EXECUTION_STATUSES = {
    "no_changes",
    "changes",
    "baseline_rebuilt",
    "not_prepared",
    "not_followed",
    "notified",
    "no_recipients",
    "notification_failed",
    "partial",
    "error",
}


def now_iso(value: datetime | None = None) -> str:
    return (value or datetime.now()).replace(microsecond=0).isoformat()


def json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_load(value: object, fallback: object) -> object:
    try:
        return json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def create_cycle(
    conn: sqlite3.Connection,
    *,
    origin: str,
    requested_by: str,
    licitacion_id: int | None = None,
    metadata: Mapping[str, object] | None = None,
) -> int:
    ensure_tender_monitor_schema(conn)
    created_at = now_iso()
    cursor = conn.execute(
        """
        INSERT INTO tender_monitor_cycles (
            origin, requested_by, requested_licitacion_id, status, created_at, metadata_json
        ) VALUES (?, ?, ?, 'pending', ?, ?)
        """,
        (origin, requested_by, licitacion_id, created_at, json_dump(dict(metadata or {}))),
    )
    return int(cursor.lastrowid)


def active_cycle(conn: sqlite3.Connection) -> sqlite3.Row | None:
    ensure_tender_monitor_schema(conn)
    return conn.execute(
        """
        SELECT * FROM tender_monitor_cycles
        WHERE status IN ('pending', 'running', 'waiting_ai', 'pending_notification')
        ORDER BY id ASC LIMIT 1
        """
    ).fetchone()


def cycle_row(conn: sqlite3.Connection, cycle_id: int) -> sqlite3.Row | None:
    ensure_tender_monitor_schema(conn)
    return conn.execute("SELECT * FROM tender_monitor_cycles WHERE id = ?", (cycle_id,)).fetchone()


def start_cycle(conn: sqlite3.Connection, cycle_id: int, *, total_count: int, timestamp: str) -> bool:
    changed = conn.execute(
        """
        UPDATE tender_monitor_cycles
        SET status = 'running', started_at = COALESCE(started_at, ?),
            heartbeat_at = ?, total_count = ?
        WHERE id = ? AND status = 'pending'
        """,
        (timestamp, timestamp, total_count, cycle_id),
    ).rowcount
    return bool(changed)


def heartbeat_cycle(
    conn: sqlite3.Connection,
    cycle_id: int,
    *,
    current_licitacion_id: int | None,
    timestamp: str,
) -> None:
    conn.execute(
        """
        UPDATE tender_monitor_cycles
        SET heartbeat_at = ?, current_licitacion_id = ?
        WHERE id = ?
        """,
        (timestamp, current_licitacion_id, cycle_id),
    )


def finish_cycle(conn: sqlite3.Connection, cycle_id: int, *, status: str, timestamp: str) -> None:
    conn.execute(
        """
        UPDATE tender_monitor_cycles
        SET status = ?, finished_at = ?, heartbeat_at = ?, current_licitacion_id = NULL
        WHERE id = ?
        """,
        (status, timestamp, timestamp, cycle_id),
    )


def increment_cycle(conn: sqlite3.Connection, cycle_id: int, **counts: int) -> None:
    allowed = {
        "processed_count",
        "no_changes_count",
        "changes_count",
        "baseline_count",
        "waiting_ai_count",
        "notified_count",
        "error_count",
        "incident_count",
    }
    updates = {key: int(value) for key, value in counts.items() if key in allowed and int(value)}
    if not updates:
        return
    clause = ", ".join(f"{key} = {key} + ?" for key in updates)
    conn.execute(f"UPDATE tender_monitor_cycles SET {clause} WHERE id = ?", [*updates.values(), cycle_id])


def create_execution(
    conn: sqlite3.Connection,
    *,
    cycle_id: int,
    licitacion_id: int,
    platform: str,
    timestamp: str,
) -> int:
    conn.execute(
        """
        INSERT OR IGNORE INTO tender_monitor_executions (
            cycle_id, licitacion_id, platform, status, started_at
        ) VALUES (?, ?, ?, 'running', ?)
        """,
        (cycle_id, licitacion_id, platform, timestamp),
    )
    row = conn.execute(
        "SELECT id FROM tender_monitor_executions WHERE cycle_id = ? AND licitacion_id = ?",
        (cycle_id, licitacion_id),
    ).fetchone()
    if not row:
        raise sqlite3.IntegrityError("No se pudo crear la ejecución de licitación.")
    return int(row["id"] if isinstance(row, sqlite3.Row) else row[0])


def finish_execution(
    conn: sqlite3.Connection,
    execution_id: int,
    *,
    status: str,
    timestamp: str,
    preparation_status: str | None = None,
    preparation_reason: str | None = None,
    previous_snapshot_id: int | None = None,
    current_snapshot_id: int | None = None,
    batch_id: int | None = None,
    ai_status: str | None = None,
    notification_status: str | None = None,
    error_phase: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    log: Iterable[object] | None = None,
) -> None:
    values: dict[str, object] = {"status": status, "finished_at": timestamp}
    optional = {
        "preparation_status": preparation_status,
        "preparation_reason": preparation_reason,
        "previous_snapshot_id": previous_snapshot_id,
        "current_snapshot_id": current_snapshot_id,
        "batch_id": batch_id,
        "ai_status": ai_status,
        "notification_status": notification_status,
        "error_phase": error_phase,
        "error_code": error_code,
        "error_message": error_message,
        "log_json": json_dump(list(log)) if log is not None else None,
    }
    values.update({key: value for key, value in optional.items() if value is not None})
    clause = ", ".join(f"{key} = ?" for key in values)
    conn.execute(
        f"UPDATE tender_monitor_executions SET {clause} WHERE id = ?",
        [*values.values(), execution_id],
    )


def latest_snapshot(conn: sqlite3.Connection, licitacion_id: int) -> tuple[int | None, dict[str, object] | None]:
    ensure_tender_monitor_schema(conn)
    row = conn.execute(
        """
        SELECT id, snapshot_json FROM tender_monitor_snapshots
        WHERE licitacion_id = ?
        ORDER BY confirmed_at DESC, id DESC LIMIT 1
        """,
        (licitacion_id,),
    ).fetchone()
    if not row:
        return None, None
    payload = json_load(row["snapshot_json"], {})
    return int(row["id"]), payload if isinstance(payload, dict) else None


def save_snapshot(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int,
    platform: str,
    snapshot: Mapping[str, object],
    source: str,
    execution_id: int | None,
    timestamp: str,
) -> int:
    fingerprint = str(snapshot.get("fingerprint") or "")
    if not fingerprint:
        raise ValueError("El snapshot técnico no tiene huella.")
    conn.execute(
        """
        INSERT OR IGNORE INTO tender_monitor_snapshots (
            licitacion_id, platform, schema_version, fingerprint,
            completeness_json, snapshot_json, source, execution_id,
            created_at, confirmed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            licitacion_id,
            platform,
            int(snapshot.get("schema_version") or 1),
            fingerprint,
            json_dump(snapshot_completeness(snapshot)),
            json_dump(dict(snapshot)),
            source,
            execution_id,
            timestamp,
            timestamp,
        ),
    )
    row = conn.execute(
        "SELECT id FROM tender_monitor_snapshots WHERE licitacion_id = ? AND fingerprint = ?",
        (licitacion_id, fingerprint),
    ).fetchone()
    if not row:
        raise sqlite3.IntegrityError("No se pudo confirmar el snapshot técnico.")
    return int(row["id"])


def create_batch(
    conn: sqlite3.Connection,
    *,
    cycle_id: int,
    execution_id: int,
    licitacion_id: int,
    platform: str,
    previous_snapshot_id: int,
    current_snapshot_id: int,
    difference_fingerprint: str,
    summary: str,
    differences: Iterable[Mapping[str, object]],
    timestamp: str,
) -> tuple[int, bool]:
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO tender_monitor_batches (
            cycle_id, execution_id, licitacion_id, platform,
            previous_snapshot_id, current_snapshot_id, difference_fingerprint,
            summary, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cycle_id,
            execution_id,
            licitacion_id,
            platform,
            previous_snapshot_id,
            current_snapshot_id,
            difference_fingerprint,
            summary,
            timestamp,
        ),
    )
    created = bool(cursor.rowcount)
    row = conn.execute(
        """
        SELECT id FROM tender_monitor_batches
        WHERE licitacion_id = ? AND difference_fingerprint = ?
        """,
        (licitacion_id, difference_fingerprint),
    ).fetchone()
    if not row:
        raise sqlite3.IntegrityError("No se pudo crear o recuperar el lote de novedades.")
    batch_id = int(row["id"])
    if created:
        for item in differences:
            conn.execute(
                """
                INSERT OR IGNORE INTO tender_monitor_differences (
                    batch_id, stable_key, block_name, change_type, item_type,
                    item_key, title, old_value_json, new_value_json,
                    ai_candidate, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    item.get("stable_key"),
                    item.get("block"),
                    item.get("change_type"),
                    item.get("item_type"),
                    item.get("item_key"),
                    item.get("title"),
                    json_dump(item.get("old_value")) if item.get("old_value") is not None else None,
                    json_dump(item.get("new_value")) if item.get("new_value") is not None else None,
                    1 if item.get("ai_candidate") else 0,
                    timestamp,
                ),
            )
    return batch_id, created


def record_incident(
    conn: sqlite3.Connection,
    *,
    cycle_id: int,
    execution_id: int | None,
    licitacion_id: int | None,
    phase: str,
    code: str,
    summary: str,
    technical_detail: str = "",
    retry_count: int = 0,
    outcome: str = "recorded",
    dedupe_key: str = "",
    timestamp: str | None = None,
) -> int:
    stamp = timestamp or now_iso()
    stable_key = dedupe_key or f"{execution_id or 0}:{phase}:{code}:{summary}"
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO tender_monitor_incidents (
            cycle_id, execution_id, licitacion_id, phase, code, summary,
            technical_detail, retry_count, outcome, dedupe_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cycle_id,
            execution_id,
            licitacion_id,
            phase,
            code,
            summary,
            technical_detail[:4000],
            retry_count,
            outcome,
            stable_key,
            stamp,
        ),
    )
    if cursor.rowcount:
        increment_cycle(conn, cycle_id, incident_count=1)
    row = conn.execute(
        "SELECT id FROM tender_monitor_incidents WHERE cycle_id = ? AND dedupe_key = ?",
        (cycle_id, stable_key),
    ).fetchone()
    return int(row["id"]) if row else 0


def recover_orphan_cycles(
    conn: sqlite3.Connection,
    *,
    timestamp: datetime,
    minutes: int,
) -> list[int]:
    """Cierra ciclos sin lease/heartbeat vigente y deja una auditoría explícita."""
    ensure_tender_monitor_schema(conn)
    current_text = now_iso(timestamp)
    cutoff_text = now_iso(timestamp - timedelta(minutes=max(5, minutes)))
    conn.execute("DELETE FROM tender_monitor_leases WHERE expires_at <= ?", (current_text,))
    lease = conn.execute(
        "SELECT metadata_json FROM tender_monitor_leases WHERE lease_key = 'tender-monitor:global'"
    ).fetchone()
    metadata = json_load(lease["metadata_json"], {}) if lease else {}
    protected_cycle_id = int(metadata.get("cycle_id") or 0) if isinstance(metadata, Mapping) else 0
    rows = conn.execute(
        """
        SELECT id, requested_licitacion_id,
               COALESCE(heartbeat_at, started_at, created_at, '') AS last_activity
        FROM tender_monitor_cycles
        WHERE status IN ('pending', 'running', 'waiting_ai', 'pending_notification')
        """
    ).fetchall()
    recovered: list[int] = []
    for row in rows:
        cycle_id = int(row["id"])
        if cycle_id == protected_cycle_id:
            continue
        last_activity = str(row["last_activity"] or "")
        if last_activity and last_activity > cutoff_text:
            continue
        finish_cycle(conn, cycle_id, status="failed", timestamp=current_text)
        record_incident(
            conn,
            cycle_id=cycle_id,
            execution_id=None,
            licitacion_id=row["requested_licitacion_id"],
            phase="recovery",
            code="ORPHAN_CYCLE_RECOVERED",
            summary="Se cerró un ciclo huérfano sin lease ni heartbeat vigente.",
            outcome="recovered",
            dedupe_key="orphan-cycle-recovered",
            timestamp=current_text,
        )
        recovered.append(cycle_id)
    return recovered


def acquire_lease(
    conn: sqlite3.Connection,
    *,
    lease_key: str,
    owner: str,
    minutes: int,
    timestamp: datetime,
    metadata: Mapping[str, object] | None = None,
) -> tuple[bool, dict[str, object] | None]:
    ensure_tender_monitor_schema(conn)
    now_text = now_iso(timestamp)
    conn.execute("DELETE FROM tender_monitor_leases WHERE expires_at <= ?", (now_text,))
    expires = now_iso(timestamp + timedelta(minutes=max(1, minutes)))
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO tender_monitor_leases (
            lease_key, owner, acquired_at, heartbeat_at, expires_at, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (lease_key, owner, now_text, now_text, expires, json_dump(dict(metadata or {}))),
    )
    if cursor.rowcount:
        return True, None
    row = conn.execute("SELECT * FROM tender_monitor_leases WHERE lease_key = ?", (lease_key,)).fetchone()
    return False, dict(row) if row else None


def refresh_lease(
    conn: sqlite3.Connection,
    *,
    lease_key: str,
    owner: str,
    minutes: int,
    timestamp: datetime,
) -> bool:
    return bool(
        conn.execute(
            """
            UPDATE tender_monitor_leases SET heartbeat_at = ?, expires_at = ?
            WHERE lease_key = ? AND owner = ?
            """,
            (
                now_iso(timestamp),
                now_iso(timestamp + timedelta(minutes=max(1, minutes))),
                lease_key,
                owner,
            ),
        ).rowcount
    )


def release_lease(conn: sqlite3.Connection, *, lease_key: str, owner: str) -> None:
    conn.execute("DELETE FROM tender_monitor_leases WHERE lease_key = ? AND owner = ?", (lease_key, owner))


def settings_payload(conn: sqlite3.Connection) -> dict[str, object]:
    ensure_tender_monitor_schema(conn)
    values = dict(SETTING_DEFAULTS)
    values.update(
        {str(row["key"]): str(row["value"] or "") for row in conn.execute("SELECT key, value FROM tender_monitor_settings")}
    )
    users = conn.execute(
        """
        SELECT u.username, u.display_name, u.email, u.role, u.active,
               COALESCE(u.telegram_chat_id, '') AS telegram_chat_id,
               COALESCE(u.telegram_notifications_enabled, 0) AS telegram_notifications_enabled,
               COALESCE(r.email_enabled, 0) AS email_enabled,
               COALESCE(r.telegram_enabled, 0) AS telegram_enabled,
               COALESCE(r.incident_admin, 0) AS incident_admin
        FROM usuarios AS u
        LEFT JOIN tender_monitor_recipients AS r ON r.username = u.username
        ORDER BY u.display_name, u.username
        """
    ).fetchall()
    return {
        "automatic_enabled": False,
        "automatic_message": "Ejecución automática desactivada. El monitor solo se ejecuta manualmente.",
        "values": values,
        "users": [
            {
                **dict(row),
                "active": bool(row["active"]),
                "email_enabled": bool(row["email_enabled"]),
                "telegram_enabled": bool(row["telegram_enabled"]),
                "incident_admin": bool(row["incident_admin"]),
            }
            for row in users
        ],
    }


def save_settings(
    conn: sqlite3.Connection,
    *,
    values: Mapping[str, object],
    users: Iterable[Mapping[str, object]],
    updated_by: str,
    timestamp: str,
) -> dict[str, object]:
    allowed = set(SETTING_DEFAULTS) - {"automatic_enabled"}
    for key, value in values.items():
        if key not in allowed:
            continue
        conn.execute(
            """
            INSERT INTO tender_monitor_settings (key, value, updated_at, updated_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                updated_at = excluded.updated_at, updated_by = excluded.updated_by
            """,
            (key, str(value or ""), timestamp, updated_by),
        )
    conn.execute(
        """
        INSERT INTO tender_monitor_settings (key, value, updated_at, updated_by)
        VALUES ('automatic_enabled', '0', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = '0', updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (timestamp, updated_by),
    )
    for item in users:
        username = str(item.get("username") or "").strip()
        if not username:
            continue
        exists = conn.execute("SELECT 1 FROM usuarios WHERE username = ?", (username,)).fetchone()
        if not exists:
            continue
        conn.execute(
            """
            INSERT INTO tender_monitor_recipients (
                username, email_enabled, telegram_enabled, incident_admin, updated_at, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET email_enabled = excluded.email_enabled,
                telegram_enabled = excluded.telegram_enabled,
                incident_admin = excluded.incident_admin,
                updated_at = excluded.updated_at, updated_by = excluded.updated_by
            """,
            (
                username,
                1 if item.get("email_enabled") else 0,
                1 if item.get("telegram_enabled") else 0,
                1 if item.get("incident_admin") else 0,
                timestamp,
                updated_by,
            ),
        )
    return settings_payload(conn)


def notification_recipients(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    ensure_tender_monitor_schema(conn)
    return conn.execute(
        """
        SELECT u.username, u.display_name, u.email, u.telegram_chat_id,
               COALESCE(u.telegram_notifications_enabled, 0) AS telegram_notifications_enabled,
               r.email_enabled, r.telegram_enabled, r.incident_admin
        FROM tender_monitor_recipients AS r
        JOIN usuarios AS u ON u.username = r.username
        WHERE u.active = 1 AND (r.email_enabled = 1 OR r.telegram_enabled = 1)
        ORDER BY u.display_name, u.username
        """
    ).fetchall()


def incident_admin_recipient(conn: sqlite3.Connection) -> sqlite3.Row | None:
    ensure_tender_monitor_schema(conn)
    return conn.execute(
        """
        SELECT u.username, u.display_name, u.email
        FROM tender_monitor_recipients AS r
        JOIN usuarios AS u ON u.username = r.username
        WHERE u.active = 1 AND u.role = 'admin' AND r.incident_admin = 1
          AND COALESCE(u.email, '') <> ''
        ORDER BY u.username LIMIT 1
        """
    ).fetchone()


def cycle_to_dict(conn: sqlite3.Connection, row: sqlite3.Row, *, detail: bool = False) -> dict[str, object]:
    item = dict(row)
    item["metadata"] = json_load(item.pop("metadata_json", "{}"), {})
    if detail:
        executions = conn.execute(
            """
            SELECT e.*, l.expediente, l.objeto, l.enlace_perfil
            FROM tender_monitor_executions AS e
            JOIN licitaciones AS l ON l.id = e.licitacion_id
            WHERE e.cycle_id = ? ORDER BY e.id
            """,
            (row["id"],),
        ).fetchall()
        item["executions"] = [execution_to_dict(conn, execution, detail=True) for execution in executions]
        item["incidents"] = [
            dict(value)
            for value in conn.execute(
                "SELECT * FROM tender_monitor_incidents WHERE cycle_id = ? ORDER BY id", (row["id"],)
            ).fetchall()
        ]
        report = conn.execute(
            "SELECT * FROM tender_monitor_incident_reports WHERE cycle_id = ?", (row["id"],)
        ).fetchone()
        item["incident_report"] = dict(report) if report else None
    return item


def execution_to_dict(conn: sqlite3.Connection, row: sqlite3.Row, *, detail: bool = False) -> dict[str, object]:
    item = dict(row)
    item["log"] = json_load(item.pop("log_json", "[]"), [])
    if detail and row["batch_id"]:
        batch = conn.execute("SELECT * FROM tender_monitor_batches WHERE id = ?", (row["batch_id"],)).fetchone()
        if batch:
            batch_item = dict(batch)
            differences = conn.execute(
                "SELECT * FROM tender_monitor_differences WHERE batch_id = ? ORDER BY id", (batch["id"],)
            ).fetchall()
            batch_item["differences"] = [
                {
                    **dict(value),
                    "old_value": json_load(value["old_value_json"], None),
                    "new_value": json_load(value["new_value_json"], None),
                }
                for value in differences
            ]
            batch_item["notifications"] = [
                dict(value)
                for value in conn.execute(
                    "SELECT * FROM tender_monitor_notifications WHERE batch_id = ? ORDER BY id", (batch["id"],)
                ).fetchall()
            ]
            batch_item["ai_links"] = [
                dict(value)
                for value in conn.execute(
                    "SELECT * FROM tender_monitor_ai_links WHERE batch_id = ? ORDER BY id", (batch["id"],)
                ).fetchall()
            ]
            item["batch"] = batch_item
    for key in ("previous_snapshot_id", "current_snapshot_id"):
        snapshot_id = row[key]
        if detail and snapshot_id:
            snapshot = conn.execute(
                "SELECT snapshot_json FROM tender_monitor_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
            item[key.removesuffix("_id")] = json_load(snapshot["snapshot_json"], {}) if snapshot else None
    return item


def list_cycles(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    status: str = "",
    licitacion_id: int | None = None,
    platform: str = "",
    date_from: str = "",
    date_to: str = "",
    with_changes: bool | None = None,
    with_incidents: bool | None = None,
    waiting_ai: bool | None = None,
    notification_failed: bool | None = None,
) -> list[dict[str, object]]:
    ensure_tender_monitor_schema(conn)
    where: list[str] = []
    params: list[object] = []
    if status:
        where.append("c.status = ?")
        params.append(status)
    if licitacion_id:
        where.append("EXISTS (SELECT 1 FROM tender_monitor_executions e WHERE e.cycle_id = c.id AND e.licitacion_id = ?)")
        params.append(licitacion_id)
    if platform:
        where.append("EXISTS (SELECT 1 FROM tender_monitor_executions e WHERE e.cycle_id = c.id AND UPPER(e.platform) = UPPER(?))")
        params.append(platform)
    if date_from:
        where.append("SUBSTR(COALESCE(c.started_at, c.created_at, ''), 1, 10) >= ?")
        params.append(date_from[:10])
    if date_to:
        where.append("SUBSTR(COALESCE(c.started_at, c.created_at, ''), 1, 10) <= ?")
        params.append(date_to[:10])
    if with_changes is not None:
        where.append("c.changes_count > 0" if with_changes else "c.changes_count = 0")
    if with_incidents is not None:
        where.append("c.incident_count > 0" if with_incidents else "c.incident_count = 0")
    if waiting_ai is not None:
        expression = "EXISTS (SELECT 1 FROM tender_monitor_executions e WHERE e.cycle_id = c.id AND e.ai_status = 'waiting')"
        where.append(expression if waiting_ai else f"NOT {expression}")
    if notification_failed is not None:
        expression = "EXISTS (SELECT 1 FROM tender_monitor_executions e WHERE e.cycle_id = c.id AND e.notification_status IN ('notification_failed', 'partial'))"
        where.append(expression if notification_failed else f"NOT {expression}")
    sql_where = "WHERE " + " AND ".join(where) if where else ""
    params.append(max(1, min(int(limit or 50), 200)))
    rows = conn.execute(
        f"SELECT c.* FROM tender_monitor_cycles c {sql_where} ORDER BY c.id DESC LIMIT ?", params
    ).fetchall()
    return [cycle_to_dict(conn, row) for row in rows]


def get_cycle(conn: sqlite3.Connection, cycle_id: int) -> dict[str, object] | None:
    row = cycle_row(conn, cycle_id)
    return cycle_to_dict(conn, row, detail=True) if row else None
