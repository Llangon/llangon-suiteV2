from __future__ import annotations

import html
import os
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from urllib.parse import quote

try:
    from .comments import create_system_comment
    from .email_templates import build_llangon_email_shell
    from .formatting import format_date_es
    from .infonalia_history import (
        SEVERITY_ATTENTION,
        SEVERITY_CRITICAL,
        SEVERITY_NORMAL,
        record_infonalia_activity,
    )
    from .infonalia_days import refresh_day_status
    from .licitacion_center import record_licitacion_history
    from .licitacion_publication import is_anuncio_previo
    from .licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_PREPARAR_FICHA,
        normalize_licitacion_estado,
    )
    from .normalization import clean_text, parse_time_value
except ImportError:
    from comments import create_system_comment
    from email_templates import build_llangon_email_shell
    from formatting import format_date_es
    from infonalia_history import (
        SEVERITY_ATTENTION,
        SEVERITY_CRITICAL,
        SEVERITY_NORMAL,
        record_infonalia_activity,
    )
    from infonalia_days import refresh_day_status
    from licitacion_center import record_licitacion_history
    from licitacion_publication import is_anuncio_previo
    from licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_DESCARTADA,
        ESTADO_ENVIADA_NURIA,
        ESTADO_IMPORTADA,
        ESTADO_PREPARAR_FICHA,
        normalize_licitacion_estado,
    )
    from normalization import clean_text, parse_time_value


ACTION_DISCARD = "01"
ACTION_DOWNLOAD_REVIEW = "02"
ACTION_PREPARE = "03"
ACTION_AI_SUMMARY = "04"
ACTION_REVIEWED = "99"

EMAIL_ACTION_EXECUTION_PENDING = "pending"
EMAIL_ACTION_EXECUTION_COMPLETED = "completed"
EMAIL_ACTION_EXECUTION_FAILED = "failed"
EMAIL_ACTION_EXECUTION_IGNORED = "ignored"
EMAIL_ACTION_DOWNLOAD_CODES = {
    ACTION_DOWNLOAD_REVIEW,
    ACTION_PREPARE,
    ACTION_AI_SUMMARY,
}

ACTION_MAILBOX_TO_DEFAULT = "info3llangon@gmail.com"
ACTION_MAILBOX_CC_DEFAULT = ""
ACTION_NOTIFY_EMAIL_DEFAULT = "info3@llangon.com"

ACTION_DEFINITIONS: dict[str, dict[str, str]] = {
    ACTION_DISCARD: {
        "name": "Descartar",
        "subject": "Descartar licitación",
        "state": ESTADO_DESCARTADA,
        "body_label": "Descartar licitación.",
        "comment": "Acción recibida desde correo de revisión Infonalia: Nuria solicitó DESCARTAR.",
    },
    ACTION_DOWNLOAD_REVIEW: {
        "name": "Descargar para ver",
        "subject": "Descargar para ver licitación",
        "state": ESTADO_DESCARGAR_PARA_VER,
        "body_label": "Descargar para ver licitación.",
        "comment": "Acción recibida desde correo de revisión Infonalia: Nuria solicitó DESCARGAR PARA VER.",
    },
    ACTION_PREPARE: {
        "name": "Preparar ficha",
        "subject": "Preparar ficha de licitación",
        "state": ESTADO_PREPARAR_FICHA,
        "body_label": "Preparar ficha de licitación.",
        "comment": "Acción recibida desde correo de revisión Infonalia: Nuria solicitó PREPARAR FICHA.",
    },
    ACTION_AI_SUMMARY: {
        "name": "Solicitar resumen IA",
        "subject": "Solicitar resumen IA de licitación",
        "state": ESTADO_DESCARGAR_PARA_VER,
        "body_label": "Solicitar resumen IA de licitación.",
        "comment": "Acción recibida desde correo de revisión Infonalia: Nuria solicitó RESUMEN IA.",
    },
    ACTION_REVIEWED: {
        "name": "Revisado",
        "subject": "Revisión Infonalia revisada",
        "state": "",
        "body_label": "Marcar como revisada la primera revisión Infonalia.",
        "comment": "",
    },
}

INITIAL_EMAIL_ACTION_STATES = {
    ESTADO_IMPORTADA,
    ESTADO_ENVIADA_NURIA,
    ESTADO_DESCARTADA,
    ESTADO_DESCARGAR_PARA_VER,
    ESTADO_PREPARAR_FICHA,
    "Preparar",
}

REVIEW_UNDECIDED_STATES = {
    ESTADO_IMPORTADA,
    ESTADO_ENVIADA_NURIA,
}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def action_mailbox_to(environ: Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    return clean_text(env.get("LLANGON_ACTION_MAILBOX_TO")) or ACTION_MAILBOX_TO_DEFAULT


def action_mailbox_cc(environ: Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    return clean_text(env.get("LLANGON_ACTION_MAILBOX_CC")) or ACTION_MAILBOX_CC_DEFAULT


def action_notify_email(environ: Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    return clean_text(env.get("LLANGON_ACTION_NOTIFY_EMAIL")) or ACTION_NOTIFY_EMAIL_DEFAULT


def review_ai_summary_button_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = environ or os.environ
    return clean_text(env.get("LLANGON_REVIEW_AI_SUMMARY_BUTTON_ENABLED") or "0").lower() in {"1", "true", "yes", "on"}


def split_emails(value: object) -> list[str]:
    result: list[str] = []
    if isinstance(value, (list, tuple, set)):
        source = []
        for item in value:
            source.extend(re.split(r"[;,\n\r]+", clean_text(item)))
    else:
        source = re.split(r"[;,\n\r]+", clean_text(value))
    for item in source:
        email = item.strip().lower()
        if email and email not in result:
            result.append(email)
    return result


def generate_action_code(entity_id: int, action_code: str) -> str:
    action = clean_text(action_code)
    if not re.fullmatch(r"\d{2}", action):
        raise ValueError("Código de acción no válido.")
    numeric_id = int(entity_id)
    if numeric_id <= 0 or numeric_id > 999_999_999:
        raise ValueError("Id interno fuera de rango para código de acción.")
    return f"{numeric_id:09d}{action}"


def extract_action_code(subject: object = "", body: object = "") -> str:
    text = f"{clean_text(body)}\n{clean_text(subject)}"
    patterns = (
        r"LLANGON_ACTION_CODE\s*=\s*(\d{11})",
        r"LLANGON_CMD\s+(\d{11})",
        r"\b(\d{11})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def ensure_email_action_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_action_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            review_id INTEGER NOT NULL,
            licitacion_id INTEGER,
            action_code TEXT NOT NULL,
            action_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            processed_at TEXT,
            processed_by_email TEXT,
            source_message_id TEXT,
            result_message TEXT,
            error_message TEXT,
            FOREIGN KEY (review_id) REFERENCES infonalia_dias(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_action_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source_message_id TEXT,
            from_email TEXT,
            subject TEXT,
            code TEXT,
            action_code TEXT,
            action_name TEXT,
            review_id INTEGER,
            licitacion_id INTEGER,
            previous_status TEXT,
            new_status TEXT,
            result TEXT NOT NULL,
            reason TEXT,
            download_job_id INTEGER,
            execution_status TEXT,
            failure_stage TEXT,
            failure_code TEXT,
            failure_detail TEXT,
            telegram_notification_attempt_count INTEGER NOT NULL DEFAULT 0,
            telegram_notification_next_attempt_at TEXT,
            telegram_notification_claimed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_ai_summary_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_action_event_id INTEGER NOT NULL UNIQUE,
            review_id INTEGER,
            licitacion_id INTEGER NOT NULL,
            download_job_id INTEGER,
            ai_job_id INTEGER,
            source_message_id TEXT,
            requested_by TEXT,
            status TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email_action_event_id) REFERENCES email_action_events(id),
            FOREIGN KEY (review_id) REFERENCES infonalia_dias(id),
            FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id),
            FOREIGN KEY (download_job_id) REFERENCES download_jobs(id)
        )
        """
    )
    code_additions = {
        "processed_at": "TEXT",
        "processed_by_email": "TEXT",
        "source_message_id": "TEXT",
        "result_message": "TEXT",
        "error_message": "TEXT",
    }
    event_additions = {
        "telegram_notification_status": "TEXT",
        "telegram_notification_attempted_at": "TEXT",
        "telegram_notification_target": "TEXT",
        "telegram_notification_error": "TEXT",
        "telegram_notification_message_id": "TEXT",
        "download_job_id": "INTEGER",
        "execution_status": "TEXT",
        "failure_stage": "TEXT",
        "failure_code": "TEXT",
        "failure_detail": "TEXT",
        "telegram_notification_attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "telegram_notification_next_attempt_at": "TEXT",
        "telegram_notification_claimed_at": "TEXT",
    }
    existing = {row[1] for row in conn.execute("PRAGMA table_info(email_action_codes)").fetchall()}
    for column, definition in code_additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE email_action_codes ADD COLUMN {column} {definition}")
    event_existing = {row[1] for row in conn.execute("PRAGMA table_info(email_action_events)").fetchall()}
    for column, definition in event_additions.items():
        if column not in event_existing:
            conn.execute(f"ALTER TABLE email_action_events ADD COLUMN {column} {definition}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_email_action_codes_code ON email_action_codes(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_codes_review ON email_action_codes(review_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_codes_licitacion ON email_action_codes(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_codes_status ON email_action_codes(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_code ON email_action_events(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_review ON email_action_events(review_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_licitacion ON email_action_events(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_created ON email_action_events(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_download_job ON email_action_events(download_job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_execution ON email_action_events(execution_status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_action_events_telegram_pending "
        "ON email_action_events(telegram_notification_status, telegram_notification_next_attempt_at)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_ai_summary_requests_download ON email_ai_summary_requests(download_job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_ai_summary_requests_status ON email_ai_summary_requests(status)")


def ensure_review_action_codes(
    conn: sqlite3.Connection,
    *,
    review_id: int,
    licitaciones: Sequence[sqlite3.Row | Mapping[str, object]],
    timestamp: str | None = None,
    ai_summary_enabled: bool | None = None,
) -> dict[tuple[int | None, str], str]:
    ensure_email_action_schema(conn)
    created_at = timestamp or now_iso()
    result: dict[tuple[int | None, str], str] = {}
    ai_summary_enabled = review_ai_summary_button_enabled() if ai_summary_enabled is None else bool(ai_summary_enabled)
    individual_actions = [ACTION_DISCARD, ACTION_DOWNLOAD_REVIEW, ACTION_PREPARE]
    if ai_summary_enabled:
        individual_actions.append(ACTION_AI_SUMMARY)

    for row in licitaciones:
        licitacion_id = int(row["id"])
        for action_code in individual_actions:
            code = generate_action_code(licitacion_id, action_code)
            action = ACTION_DEFINITIONS[action_code]
            conn.execute(
                """
                INSERT OR IGNORE INTO email_action_codes (
                    code, review_id, licitacion_id, action_code, action_name, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (code, review_id, licitacion_id, action_code, action["name"], created_at),
            )
            result[(licitacion_id, action_code)] = code

    review_code = generate_action_code(review_id, ACTION_REVIEWED)
    conn.execute(
        """
        INSERT OR IGNORE INTO email_action_codes (
            code, review_id, licitacion_id, action_code, action_name, status, created_at
        )
        VALUES (?, ?, NULL, ?, ?, 'pending', ?)
        """,
        (review_code, review_id, ACTION_REVIEWED, ACTION_DEFINITIONS[ACTION_REVIEWED]["name"], created_at),
    )
    result[(None, ACTION_REVIEWED)] = review_code
    return result


def _row_value(row: sqlite3.Row | Mapping[str, object], key: str, default: object = "") -> object:
    try:
        if key in row.keys():  # type: ignore[attr-defined]
            return row[key]
    except AttributeError:
        if key in row:
            return row[key]
    return default


def _format_money(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} €"


def _date_time_label(row: sqlite3.Row | Mapping[str, object]) -> str:
    date_label = format_date_es(_row_value(row, "fecha_limite"))
    time_label = parse_time_value(_row_value(row, "hora_limite"))
    if not date_label and not time_label:
        return "No consta"
    time_label = time_label or "Sin hora"
    return f"{date_label} - {time_label}" if date_label else time_label


def _parse_deadline(row: sqlite3.Row | Mapping[str, object]) -> datetime | None:
    raw_date = clean_text(_row_value(row, "fecha_limite"))
    if not raw_date:
        return None
    raw_time = parse_time_value(_row_value(row, "hora_limite")) or "23:59"
    try:
        return datetime.fromisoformat(f"{raw_date}T{raw_time}")
    except ValueError:
        return None


def _days_badge(row: sqlite3.Row | Mapping[str, object], *, generated_at: datetime) -> tuple[str, str, str]:
    deadline = _parse_deadline(row)
    if not deadline:
        return "", "#f3f4f6", "#475467"
    if deadline < generated_at:
        return "Vencida", "#fee2e2", "#991b1b"
    days = (deadline.date() - generated_at.date()).days
    label = "Vence hoy" if days == 0 else f"Vence en {days} día" if days == 1 else f"Vence en {days} días"
    if days <= 2:
        return label, "#fee2e2", "#991b1b"
    if days <= 7:
        return label, "#fff7cc", "#8a5b00"
    return label, "#e8f7ff", "#075985"


def _mailto(to_email: str, subject: str, body: str, *, cc: str = "") -> str:
    query = f"subject={quote(subject)}&body={quote(body)}"
    if clean_text(cc):
        query = f"cc={quote(clean_text(cc))}&{query}"
    return f"mailto:{quote(clean_text(to_email))}?{query}"


def build_licitacion_action_subject(row: sqlite3.Row | Mapping[str, object], action_code: str) -> str:
    action = ACTION_DEFINITIONS[action_code]
    expediente = clean_text(_row_value(row, "expediente")) or f"ID {row['id']}"
    return f"LLANGON_CMD {generate_action_code(int(row['id']), action_code)} - {action['subject']} {expediente}"


def build_licitacion_action_body(
    row: sqlite3.Row | Mapping[str, object],
    *,
    review_id: int,
    review_date: object,
    action_code: str,
) -> str:
    action = ACTION_DEFINITIONS[action_code]
    code = generate_action_code(int(row["id"]), action_code)
    return "\n".join(
        [
            f"LLANGON_ACTION_CODE={code}",
            "",
            "Acción solicitada por Nuria:",
            action["body_label"],
            "",
            "Licitación:",
            f"ID interno: {row['id']}",
            f"Expediente: {clean_text(_row_value(row, 'expediente'))}",
            f"Título: {clean_text(_row_value(row, 'objeto'))}",
            "",
            "Origen:",
            f"Revisión Infonalia: {review_id}",
            f"Fecha: {format_date_es(review_date)}",
            "",
            "Este correo ha sido generado automáticamente desde un botón de acción de Llangón Suite.",
        ]
    )


def build_review_action_subject(review_id: int) -> str:
    return f"LLANGON_CMD {generate_action_code(review_id, ACTION_REVIEWED)} - Revisión Infonalia revisada"


def build_review_action_body(
    *,
    review_id: int,
    review_date: object,
    total_items: int,
) -> str:
    return "\n".join(
        [
            f"LLANGON_ACTION_CODE={generate_action_code(review_id, ACTION_REVIEWED)}",
            "",
            "Acción solicitada por Nuria:",
            "Marcar como revisada la primera revisión Infonalia.",
            "",
            "Revisión:",
            f"ID interno: {review_id}",
            f"Fecha: {format_date_es(review_date)}",
            f"Total licitaciones incluidas: {total_items}",
            "",
            "Efecto previsto:",
            "La Suite marcará esta revisión como revisada.",
            "Las licitaciones incluidas que sigan sin decisión, en estado Importada o Enviada a Nuria, se marcarán automáticamente como Descartada.",
            "",
            "Este correo ha sido generado automáticamente desde un botón de acción de Llangón Suite.",
        ]
    )


def _link_html(url: object, label: str) -> str:
    safe_url = html.escape(clean_text(url), quote=True)
    if not safe_url:
        return ""
    return (
        f"<a href='{safe_url}' style='display:inline-block; color:#0066cc; "
        "font-size:13px; font-weight:700; text-decoration:underline; margin-right:14px;'>"
        f"{html.escape(label)}</a>"
    )


def _button_html(href: str, label: str, *, color: str, background: str) -> str:
    return (
        f"<a href='{html.escape(href, quote=True)}' "
        f"style='display:inline-block; background:{background}; color:{color}; text-decoration:none; "
        "padding:9px 12px; border-radius:6px; font-weight:800; font-size:13px; margin:4px 6px 0 0; "
        "border:1px solid rgba(0,0,0,0.08);'>"
        f"{html.escape(label)}</a>"
    )


def build_infonalia_review_email_html(
    *,
    day: sqlite3.Row | Mapping[str, object],
    licitaciones: Sequence[sqlite3.Row | Mapping[str, object]],
    action_codes: Mapping[tuple[int | None, str], str],
    mailbox_to: str,
    mailbox_cc: str,
    generated_at: datetime | None = None,
    ai_summary_enabled: bool | None = None,
) -> str:
    generated_at = generated_at or datetime.now().replace(microsecond=0)
    ai_summary_enabled = review_ai_summary_button_enabled() if ai_summary_enabled is None else bool(ai_summary_enabled)
    rows = sorted(
        licitaciones,
        key=lambda row: (
            1 if is_anuncio_previo(_row_value(row, "tipo_publicacion")) else 0,
            clean_text(_row_value(row, "fecha_limite")) or "9999-99-99",
            parse_time_value(_row_value(row, "hora_limite")) or "99:99",
            int(_row_value(row, "id", 0) or 0),
        ),
    )
    fecha = _row_value(day, "fecha")
    saludo = "Buenos días," if 6 <= generated_at.hour < 12 else "Buenas tardes," if generated_at.hour < 20 else "Buenas noches,"
    fecha_texto = format_date_es(fecha)
    intro = (
        f"<p style='margin:0 0 12px 0;'>{html.escape(saludo)}</p>"
        f"<p style='margin:0 0 12px 0;'>Te adjunto las licitaciones de Infonalia correspondientes al día {html.escape(fecha_texto)}.</p>"
        f"<p style='margin:0 0 18px 0;'>He incluido {len(rows)} expediente(s), ordenados por fecha límite de presentación.</p>"
    )
    if not rows:
        intro += (
            "<div style='margin:0 0 18px 0; padding:14px 16px; background:#f1fff2; border:1px solid #d7e7d8; "
            "border-radius:8px; color:#0e7f15; font-size:15px; font-weight:800;'>NO HAY LICITACIONES INTERESANTES</div>"
        )

    cards: list[str] = []
    previous_notice_cards: list[str] = []
    for row in rows:
        licitacion_id = int(row["id"])
        previous_notice = is_anuncio_previo(_row_value(row, "tipo_publicacion"))
        badge_text, badge_bg, badge_color = _days_badge(row, generated_at=generated_at)
        tipo = clean_text(_row_value(row, "tipo"))
        expediente = clean_text(_row_value(row, "expediente")) or f"ID {licitacion_id}"
        objeto = clean_text(_row_value(row, "objeto"))
        organismo = clean_text(_row_value(row, "organismo"))
        provincia = clean_text(_row_value(row, "provincia"))
        presupuesto = _format_money(_row_value(row, "presupuesto"))
        fecha_limite = _date_time_label(row)
        badges = ""
        if badge_text:
            badges += (
                f"<span style='display:inline-block; background:{badge_bg}; color:{badge_color}; border:1px solid {badge_color}; "
                "padding:4px 7px; border-radius:4px; font-size:12px; font-weight:800; margin-left:4px;'>"
                f"{html.escape(badge_text)}</span>"
            )
        if tipo:
            badges += (
                "<span style='display:inline-block; background:#e7f8ea; color:#087a20; border:1px solid #8fd19e; "
                "padding:4px 7px; border-radius:4px; font-size:12px; font-weight:800; margin-left:4px;'>"
                f"{html.escape(tipo)}</span>"
            )
        if previous_notice:
            badges += (
                "<span style='display:inline-block; background:#f3f4f6; color:#374151; border:1px solid #9ca3af; "
                "padding:4px 7px; border-radius:4px; font-size:12px; font-weight:800; margin-left:4px;'>"
                "Anuncio previo</span>"
            )
        links = (
            _link_html(_row_value(row, "enlace_perfil"), "Perfil del contratante")
            + _link_html(_row_value(row, "enlace_infonalia"), "Anuncio Infonalia")
        )
        buttons = []
        action_specs = [
            (ACTION_DISCARD, "#991b1b", "#fee2e2"),
        ] if previous_notice else [
            (ACTION_DISCARD, "#991b1b", "#fee2e2"),
            (ACTION_DOWNLOAD_REVIEW, "#0f5b8d", "#e8f7ff"),
            (ACTION_PREPARE, "#0e7f15", "#e7f8ea"),
        ]
        if ai_summary_enabled and not previous_notice and (licitacion_id, ACTION_AI_SUMMARY) in action_codes:
            action_specs.append((ACTION_AI_SUMMARY, "#5b21b6", "#f3e8ff"))
        for action_code, color, bg in action_specs:
            href = _mailto(
                mailbox_to,
                build_licitacion_action_subject(row, action_code),
                build_licitacion_action_body(row, review_id=int(day["id"]), review_date=fecha, action_code=action_code),
                cc=mailbox_cc,
            )
            buttons.append(_button_html(href, ACTION_DEFINITIONS[action_code]["name"], color=color, background=bg))

        card_html = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:0 0 18px 0; "
            "background:#ffffff; border:1px solid #d9e2ec; border-left:5px solid #2f80d1;'>"
            "<tr><td style='padding:16px 18px;'>"
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;'><tr>"
            "<td style='vertical-align:top;'>"
            "<p style='margin:0 0 4px 0; color:#667085; font-size:11px; font-weight:800; text-transform:uppercase;'>Expediente</p>"
            f"<h2 style='margin:0; color:#111827; font-size:19px; line-height:1.2;'>{html.escape(expediente)}</h2>"
            "</td>"
            f"<td align='right' style='vertical-align:top; white-space:nowrap;'>{badges}</td>"
            "</tr></table>"
            f"<p style='margin:16px 0 12px 0; color:#111827; font-size:14px; line-height:1.35; font-weight:700;'>{html.escape(objeto)}</p>"
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; border-top:1px solid #d9e2ec; border-bottom:1px solid #d9e2ec;'>"
            "<tr>"
            f"<td style='width:50%; padding:12px 8px 10px 0; vertical-align:top;'><p style='margin:0 0 6px 0; color:#667085; font-size:11px; font-weight:800; text-transform:uppercase;'>Organismo</p><p style='margin:0; color:#1f2937; font-size:13px; line-height:1.35;'>{html.escape(organismo)}</p></td>"
            f"<td style='width:50%; padding:12px 0 10px 8px; vertical-align:top;'><p style='margin:0 0 6px 0; color:#667085; font-size:11px; font-weight:800; text-transform:uppercase;'>Provincia</p><p style='margin:0; color:#1f2937; font-size:13px;'>{html.escape(provincia)}</p></td>"
            "</tr><tr>"
            f"<td style='width:50%; padding:10px 8px 12px 0; vertical-align:top;'><p style='margin:0 0 6px 0; color:#667085; font-size:11px; font-weight:800; text-transform:uppercase;'>Presupuesto</p><p style='margin:0; color:#1f2937; font-size:13px;'>{html.escape(presupuesto)}</p></td>"
            f"<td style='width:50%; padding:10px 0 12px 8px; vertical-align:top;'><p style='margin:0 0 6px 0; color:#667085; font-size:11px; font-weight:800; text-transform:uppercase;'>Fecha límite</p><p style='margin:0; color:#1f2937; font-size:13px;'>{html.escape(fecha_limite)}</p></td>"
            "</tr></table>"
            f"<div style='margin-top:12px;'>{links}</div>"
            f"<div style='margin-top:12px;'>{''.join(buttons)}</div>"
            "</td></tr></table>"
        )
        if previous_notice:
            previous_notice_cards.append(card_html)
        else:
            cards.append(card_html)

    review_href = _mailto(
        mailbox_to,
        build_review_action_subject(int(day["id"])),
        build_review_action_body(review_id=int(day["id"]), review_date=fecha, total_items=len(rows)),
    )
    reviewed_button = (
        "<div style='margin:18px 0 4px 0; padding-top:14px; border-top:1px solid #d9e2ec;'>"
        f"{_button_html(review_href, 'Revisado', color='#ffffff', background='#19b51f')}"
        "</div>"
    )
    previous_notice_html = ""
    if previous_notice_cards:
        previous_notice_html = (
            "<div style='margin:24px 0 10px 0; padding-top:16px; border-top:1px solid #d9e2ec;'>"
            "<p style='margin:0; color:#374151; font-size:13px; font-weight:900; text-transform:uppercase;'>"
            "Anuncios previos</p>"
            "<p style='margin:6px 0 14px 0; color:#667085; font-size:13px;'>"
            "No consta fecha de presentación ni documentación de licitación; solo queda disponible la opción de descartar.</p>"
            "</div>"
            + "".join(previous_notice_cards)
        )
    body_html = intro + "".join(cards) + previous_notice_html + reviewed_button
    return build_llangon_email_shell(
        eyebrow="",
        title="Asesores Llangón S.L.",
        subtitle="Resumen de licitaciones Infonalia",
        body_html=body_html,
        footer_left_html="Llangón Web App",
        footer_right_html=html.escape(fecha_texto),
        closing_html="Este correo se ha generado automáticamente desde el panel privado de Asesores Llangón.",
    )


def sender_is_allowed(sender_email: str, allowed_senders: Sequence[str] | str | None) -> bool:
    allowed = split_emails(allowed_senders or "")
    if not allowed:
        return False
    return clean_text(sender_email).lower() in allowed


def action_code_row(conn: sqlite3.Connection, code: str) -> sqlite3.Row | None:
    ensure_email_action_schema(conn)
    normalized_code = clean_text(code)
    if not re.fullmatch(r"\d{11}", normalized_code):
        return None
    return conn.execute("SELECT * FROM email_action_codes WHERE code = ?", (normalized_code,)).fetchone()


def parse_action_code(code: str) -> dict[str, object]:
    normalized_code = clean_text(code)
    payload: dict[str, object] = {
        "code": normalized_code,
        "well_formed": False,
        "entity_id": None,
        "action_code": "",
        "action_name": "",
        "kind": "",
        "reason": "",
    }
    if not re.fullmatch(r"\d{11}", normalized_code):
        payload["reason"] = "código inválido"
        return payload
    action_code = normalized_code[-2:]
    action = ACTION_DEFINITIONS.get(action_code)
    payload.update(
        {
            "well_formed": True,
            "entity_id": int(normalized_code[:9]),
            "action_code": action_code,
            "action_name": action["name"] if action else "",
            "kind": "revision" if action_code == ACTION_REVIEWED else "licitacion",
        }
    )
    if not action:
        payload["reason"] = "acción no reconocida"
    return payload


def _normalize_state_for_email_action(value: object) -> str:
    raw = clean_text(value)
    if raw == "Preparar":
        return "Preparar"
    return normalize_licitacion_estado(raw, default=raw)


def _review_is_open(day: sqlite3.Row | Mapping[str, object] | None) -> bool:
    return bool(day and not clean_text(day["reviewed_at"]))


def _insert_email_action_event(
    conn: sqlite3.Connection,
    *,
    created_at: str,
    source_message_id: str = "",
    from_email: str = "",
    subject: str = "",
    code: str = "",
    action_code: str = "",
    action_name: str = "",
    review_id: int | None = None,
    licitacion_id: int | None = None,
    previous_status: str = "",
    new_status: str = "",
    result: str,
    reason: str = "",
    download_job_id: int | None = None,
    execution_status: str = "",
    failure_stage: str = "",
    failure_code: str = "",
    failure_detail: str = "",
) -> int:
    ensure_email_action_schema(conn)
    normalized_result = clean_text(result)
    normalized_execution_status = clean_text(execution_status)
    if not normalized_execution_status:
        if normalized_result == "error":
            normalized_execution_status = EMAIL_ACTION_EXECUTION_FAILED
        elif normalized_result == "ignored":
            normalized_execution_status = EMAIL_ACTION_EXECUTION_IGNORED
        elif action_code in EMAIL_ACTION_DOWNLOAD_CODES:
            normalized_execution_status = EMAIL_ACTION_EXECUTION_PENDING
        else:
            normalized_execution_status = EMAIL_ACTION_EXECUTION_COMPLETED
    telegram_status = "pending" if normalized_execution_status == EMAIL_ACTION_EXECUTION_FAILED else ""
    cur = conn.execute(
        """
        INSERT INTO email_action_events (
            created_at, source_message_id, from_email, subject, code, action_code,
            action_name, review_id, licitacion_id, previous_status, new_status,
            result, reason, download_job_id, execution_status, failure_stage,
            failure_code, failure_detail, telegram_notification_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            created_at,
            clean_text(source_message_id),
            clean_text(from_email).lower(),
            clean_text(subject),
            clean_text(code),
            clean_text(action_code),
            clean_text(action_name),
            review_id,
            licitacion_id,
            clean_text(previous_status),
            clean_text(new_status),
            normalized_result,
            clean_text(reason),
            download_job_id,
            normalized_execution_status,
            clean_text(failure_stage),
            clean_text(failure_code),
            clean_text(failure_detail or (reason if normalized_execution_status == EMAIL_ACTION_EXECUTION_FAILED else ""))[:2000],
            telegram_status,
        ),
    )
    return int(cur.lastrowid)


def _create_email_ai_summary_request(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    review_id: int,
    licitacion_id: int,
    download_request: Mapping[str, object] | None,
    source_message_id: str,
    sender_email: str,
    timestamp: str,
) -> int:
    queue = download_request.get("queue") if isinstance(download_request, Mapping) else None
    queue = queue if isinstance(queue, Mapping) else {}
    raw_job_id = queue.get("job_id")
    try:
        download_job_id = int(raw_job_id) if raw_job_id is not None else None
    except (TypeError, ValueError):
        download_job_id = None
    queue_status = clean_text(queue.get("status"))
    status = "download_pending" if download_job_id and queue_status in {"queued", "already_pending"} else "download_failed"
    detail = clean_text(queue.get("message")) or queue_status or "No se pudo vincular la descarga requerida para el resumen IA."
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO email_ai_summary_requests (
            email_action_event_id, review_id, licitacion_id, download_job_id, ai_job_id,
            source_message_id, requested_by, status, detail, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            review_id or None,
            licitacion_id,
            download_job_id,
            clean_text(source_message_id),
            clean_text(sender_email).lower(),
            status,
            detail,
            timestamp,
            timestamp,
        ),
    )
    if cur.lastrowid:
        return int(cur.lastrowid)
    row = conn.execute(
        "SELECT id FROM email_ai_summary_requests WHERE email_action_event_id = ?",
        (event_id,),
    ).fetchone()
    return int(row["id"]) if row else 0


def _processed_email_action_event(
    conn: sqlite3.Connection,
    *,
    code: str,
    source_message_id: str,
) -> sqlite3.Row | None:
    message_id = clean_text(source_message_id)
    if not message_id:
        return None
    ensure_email_action_schema(conn)
    return conn.execute(
        """
        SELECT *
        FROM email_action_events
        WHERE code = ?
          AND source_message_id = ?
          AND result = 'processed'
        ORDER BY id ASC
        LIMIT 1
        """,
        (clean_text(code), message_id),
    ).fetchone()


def check_action_code(
    conn: sqlite3.Connection,
    *,
    code: str,
    sender_email: str = "",
    allowed_senders: Sequence[str] | str | None = None,
) -> dict[str, object]:
    ensure_email_action_schema(conn)
    parsed = parse_action_code(code)
    payload: dict[str, object] = {
        **parsed,
        "exists": False,
        "licitacion_id": None,
        "review_id": None,
        "review_status": "",
        "licitacion_status": "",
        "allowed_senders_configured": bool(split_emails(allowed_senders or "")),
        "sender_authorized": None,
        "processable": False,
        "late_closed_review": False,
    }
    if not parsed["well_formed"]:
        return payload
    action_code = clean_text(parsed["action_code"])
    action = ACTION_DEFINITIONS.get(action_code)
    if not action:
        return payload
    if action_code == ACTION_AI_SUMMARY and not review_ai_summary_button_enabled():
        payload["reason"] = "resumen IA por correo desactivado"
        return payload
    payload["sender_authorized"] = sender_is_allowed(sender_email, allowed_senders) if sender_email else None

    entity_id = int(parsed["entity_id"] or 0)
    if action_code == ACTION_REVIEWED:
        day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (entity_id,)).fetchone()
        payload["review_id"] = entity_id
        if not day:
            payload["reason"] = "revisión inexistente"
            return payload
        payload["exists"] = True
        payload["review_status"] = "abierta" if _review_is_open(day) else "revisada"
        if not _review_is_open(day):
            payload["reason"] = "revisión Infonalia ya cerrada"
            return payload
        if not payload["allowed_senders_configured"]:
            payload["reason"] = "sin remitentes autorizados configurados"
            return payload
        if sender_email and not payload["sender_authorized"]:
            payload["reason"] = "remitente no autorizado"
            return payload
        payload["processable"] = True
        payload["reason"] = "revisión abierta y procesable"
        return payload

    licitacion = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (entity_id,)).fetchone()
    payload["licitacion_id"] = entity_id
    if not licitacion:
        payload["reason"] = "licitación inexistente"
        return payload
    payload["exists"] = True
    state = _normalize_state_for_email_action(licitacion["estado"])
    payload["licitacion_status"] = state
    review_id = int(licitacion["infonalia_dia_id"] or 0)
    payload["review_id"] = review_id or None
    if not review_id:
        payload["reason"] = "licitación sin revisión Infonalia asociada"
        return payload
    day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (review_id,)).fetchone()
    if not day:
        payload["reason"] = "revisión inexistente"
        return payload
    review_is_open = _review_is_open(day)
    payload["review_status"] = "abierta" if review_is_open else "revisada"
    payload["late_closed_review"] = not review_is_open
    if state not in INITIAL_EMAIL_ACTION_STATES:
        payload["reason"] = "estado avanzado no modificable desde correo"
        return payload
    if not payload["allowed_senders_configured"]:
        payload["reason"] = "sin remitentes autorizados configurados"
        return payload
    if sender_email and not payload["sender_authorized"]:
        payload["reason"] = "remitente no autorizado"
        return payload
    payload["processable"] = True
    payload["reason"] = (
        "revisión abierta y licitación procesable"
        if review_is_open
        else "revisión cerrada y acción individual tardía procesable"
    )
    return payload


def _mark_action(
    conn: sqlite3.Connection,
    row_id: int,
    *,
    status: str,
    timestamp: str,
    sender_email: str,
    source_message_id: str,
    result_message: str = "",
    error_message: str = "",
) -> None:
    conn.execute(
        """
        UPDATE email_action_codes
        SET status = ?,
            processed_at = ?,
            processed_by_email = ?,
            source_message_id = ?,
            result_message = ?,
            error_message = ?
        WHERE id = ?
        """,
        (status, timestamp, clean_text(sender_email), clean_text(source_message_id), result_message, error_message, row_id),
    )


def _same_message_already_processed(
    conn: sqlite3.Connection,
    *,
    code_row: sqlite3.Row | None,
    source_message_id: str,
) -> bool:
    if not code_row:
        return False
    if clean_text(code_row["status"]).lower() != "processed":
        return False
    current_message_id = clean_text(source_message_id)
    if not current_message_id:
        return False
    return clean_text(code_row["source_message_id"]) == current_message_id


def _request_automatic_download_after_email_action(
    conn: sqlite3.Connection,
    *,
    licitacion_id: int,
    action_code: str,
    sender_email: str,
    source_message_id: str,
    timestamp: str,
    start_worker: bool = True,
) -> dict[str, object]:
    if action_code not in {ACTION_DOWNLOAD_REVIEW, ACTION_PREPARE, ACTION_AI_SUMMARY}:
        return {"requested": False, "reason": "action_without_download"}
    try:
        try:
            from . import app as app_module
        except ImportError:
            import app as app_module  # type: ignore

        queue_result = app_module.request_licitacion_download(
            conn,
            licitacion_id,
            timestamp=timestamp,
            request_source=app_module.DOWNLOAD_REQUEST_SOURCE_EMAIL_ACTION,
            request_action=ACTION_DEFINITIONS[action_code]["name"],
            request_message_id=source_message_id,
            requested_by=sender_email,
        )
        worker_result: dict[str, object] | None = None
        if start_worker and queue_result.get("created") and queue_result.get("job_id"):
            worker_result = app_module.start_download_worker(job_id=int(queue_result["job_id"]))
        return {
            "requested": True,
            "queue": queue_result,
            "worker": worker_result or {},
        }
    except Exception as exc:
        return {
            "requested": True,
            "queue": {
                "ok": False,
                "status": "error",
                "message": f"No se pudo solicitar la descarga automática: {exc}",
            },
            "worker": {},
        }


def _process_individual_action(
    conn: sqlite3.Connection,
    *,
    code: str,
    action_code: str,
    licitacion_id: int,
    sender_email: str,
    source_message_id: str,
    subject: str,
    timestamp: str,
) -> dict[str, object]:
    action = ACTION_DEFINITIONS[action_code]
    new_state = action["state"]
    licitacion = conn.execute("SELECT * FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
    if not licitacion:
        error = "Licitación no encontrada."
        _insert_email_action_event(
            conn,
            created_at=timestamp,
            source_message_id=source_message_id,
            from_email=sender_email,
            subject=subject,
            code=code,
            action_code=action_code,
            action_name=action["name"],
            licitacion_id=licitacion_id,
            result="error",
            reason=error,
        )
        return {"status": "error", "error_code": "LICITACION_NOT_FOUND", "message": error}

    old_state = _normalize_state_for_email_action(licitacion["estado"])
    review_id = int(licitacion["infonalia_dia_id"] or 0)
    day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (review_id,)).fetchone() if review_id else None
    if not day:
        message = "Orden ignorada: revisión Infonalia inexistente."
        event_id = _insert_email_action_event(
            conn,
            created_at=timestamp,
            source_message_id=source_message_id,
            from_email=sender_email,
            subject=subject,
            code=code,
            action_code=action_code,
            action_name=action["name"],
            review_id=review_id or None,
            licitacion_id=licitacion_id,
            previous_status=old_state,
            new_status=old_state,
            result="error",
            reason=message,
        )
        record_infonalia_activity(
            conn,
            category="nuria_action",
            event_type="review_not_found",
            source="email",
            actor=sender_email,
            result="error",
            title="Orden de Nuria sin Día Infonalia disponible",
            detail=message,
            licitacion_id=licitacion_id,
            severity=SEVERITY_CRITICAL,
            dedupe_key=f"email_action:{event_id}",
            timestamp=timestamp,
        )
        return {"status": "error", "error_code": "REVIEW_NOT_FOUND", "message": message}
    review_was_closed = not _review_is_open(day)
    if old_state not in INITIAL_EMAIL_ACTION_STATES:
        message = "Orden ignorada: la licitación está en estado avanzado y no puede modificarse desde correo de revisión."
        _insert_email_action_event(
            conn,
            created_at=timestamp,
            source_message_id=source_message_id,
            from_email=sender_email,
            subject=subject,
            code=code,
            action_code=action_code,
            action_name=action["name"],
            review_id=review_id,
            licitacion_id=licitacion_id,
            previous_status=old_state,
            new_status=old_state,
            result="ignored",
            reason=message,
        )
        return {"status": "ignored", "error_code": "ADVANCED_STATE", "message": message}
    if is_anuncio_previo(_row_value(licitacion, "tipo_publicacion")) and action_code != ACTION_DISCARD:
        message = "Orden ignorada: los anuncios previos solo admiten descartar desde correo de revisión."
        _insert_email_action_event(
            conn,
            created_at=timestamp,
            source_message_id=source_message_id,
            from_email=sender_email,
            subject=subject,
            code=code,
            action_code=action_code,
            action_name=action["name"],
            review_id=review_id,
            licitacion_id=licitacion_id,
            previous_status=old_state,
            new_status=old_state,
            result="ignored",
            reason=message,
        )
        return {"status": "ignored", "error_code": "PREVIOUS_NOTICE_ACTION_NOT_ALLOWED", "message": message}

    changed = old_state != new_state
    if old_state != new_state:
        conn.execute(
            "UPDATE licitaciones SET estado = ?, updated_at = ? WHERE id = ?",
            (new_state, timestamp, licitacion_id),
        )
        record_licitacion_history(
            conn,
            licitacion_id,
            event_type="estado",
            old_value=old_state,
            new_value=new_state,
            user_id=sender_email,
            timestamp=timestamp,
        )
        create_system_comment(
            conn,
            entity_type="licitacion",
            entity_id=licitacion_id,
            body=(
                f"{action['comment']} Estado anterior: {old_state}. "
                f"Estado nuevo: {new_state}."
            ),
            metadata={
                "event_type": "email_action",
                "code": code,
                "action_code": action_code,
                "sender_email": clean_text(sender_email),
            },
            timestamp=timestamp,
        )
    refresh_day_status(conn, review_id, timestamp=timestamp)
    download_request = _request_automatic_download_after_email_action(
        conn,
        licitacion_id=licitacion_id,
        action_code=action_code,
        sender_email=sender_email,
        source_message_id=source_message_id,
        timestamp=timestamp,
        start_worker=False,
    )
    message = f"Acción {action['name']} aplicada a la licitación {licitacion_id}."
    if review_was_closed:
        message += " La decisión se recibió después del cierre del Día Infonalia."
    queue_info = download_request.get("queue") if isinstance(download_request, dict) else None
    if isinstance(queue_info, Mapping) and action_code in {ACTION_DOWNLOAD_REVIEW, ACTION_PREPARE, ACTION_AI_SUMMARY}:
        queue_status = clean_text(queue_info.get("status"))
        if queue_status == "queued":
            message += f" Descarga automática encolada (trabajo {queue_info.get('job_id')})."
        elif queue_status == "already_pending":
            message += f" Descarga automática ya pendiente (trabajo {queue_info.get('job_id')})."
        elif queue_status == "already_downloaded":
            message += " La documentación ya estaba descargada."
        elif queue_status == "error":
            message += f" Error al solicitar la descarga automática: {clean_text(queue_info.get('message'))}."
        if action_code == ACTION_AI_SUMMARY and queue_status in {"queued", "already_pending"}:
            message += " El resumen IA se enviará por correo cuando termine el análisis."
    worker_info = download_request.get("worker") if isinstance(download_request, dict) else None
    if isinstance(worker_info, Mapping) and queue_info and clean_text(queue_info.get("status")) == "queued":
        if worker_info.get("started") is False:
            message += f" Worker de descarga no iniciado automáticamente: {clean_text(worker_info.get('error'))}."
    download_job_id = 0
    if isinstance(queue_info, Mapping):
        try:
            download_job_id = int(queue_info.get("job_id") or 0)
        except (TypeError, ValueError):
            download_job_id = 0
    execution_status = ""
    failure_stage = ""
    failure_code = ""
    failure_detail = ""
    if action_code in EMAIL_ACTION_DOWNLOAD_CODES:
        execution_status = EMAIL_ACTION_EXECUTION_PENDING
        queue_status = clean_text(queue_info.get("status")) if isinstance(queue_info, Mapping) else ""
        queue_ok = bool(queue_info.get("ok")) if isinstance(queue_info, Mapping) else False
        if not queue_ok or queue_status in {"error", "failed", "skipped"}:
            execution_status = EMAIL_ACTION_EXECUTION_FAILED
            failure_stage = "queue"
            failure_code = clean_text(queue_info.get("error_code")) if isinstance(queue_info, Mapping) else "DOWNLOAD_QUEUE_ERROR"
            failure_code = failure_code or "DOWNLOAD_QUEUE_ERROR"
            failure_detail = (
                clean_text(queue_info.get("message"))
                if isinstance(queue_info, Mapping)
                else "No se pudo crear el trabajo de descarga."
            )
        elif queue_status == "already_downloaded":
            execution_status = EMAIL_ACTION_EXECUTION_COMPLETED
        elif isinstance(worker_info, Mapping) and worker_info.get("started") is False:
            execution_status = EMAIL_ACTION_EXECUTION_FAILED
            failure_stage = "worker_start"
            failure_code = "DOWNLOAD_WORKER_START_FAILED"
            failure_detail = clean_text(worker_info.get("error")) or "No se pudo iniciar el proceso de descarga."
            if download_job_id:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET status = 'failed', error_message = ?, finished_at = ?, updated_at = ?
                    WHERE id = ? AND status IN ('pending', 'running')
                    """,
                    (failure_detail[:2000], timestamp, timestamp, download_job_id),
                )
    event_id = _insert_email_action_event(
        conn,
        created_at=timestamp,
        source_message_id=source_message_id,
        from_email=sender_email,
        subject=subject,
        code=code,
        action_code=action_code,
        action_name=action["name"],
        review_id=review_id,
        licitacion_id=licitacion_id,
        previous_status=old_state,
        new_status=new_state,
        result="processed",
        reason=message,
        download_job_id=download_job_id or None,
        execution_status=execution_status,
        failure_stage=failure_stage,
        failure_code=failure_code,
        failure_detail=failure_detail,
    )
    record_infonalia_activity(
        conn,
        category="nuria_action",
        event_type="late_decision_change" if review_was_closed and changed else "email_action",
        source="email",
        actor=sender_email,
        result="processed",
        title=(
            "Cambio de decisión de Nuria posterior al cierre"
            if review_was_closed and changed
            else "Orden de Nuria posterior al cierre"
            if review_was_closed
            else f"Orden de Nuria: {action['name']}"
        ),
        detail=message,
        day_id=review_id,
        licitacion_id=licitacion_id,
        old_value=old_state,
        new_value=new_state,
        severity=(
            SEVERITY_CRITICAL
            if review_was_closed and changed
            else SEVERITY_ATTENTION
            if review_was_closed
            else SEVERITY_NORMAL
        ),
        metadata={
            "email_action_event_id": event_id,
            "action_code": action_code,
            "source_message_id": clean_text(source_message_id),
        },
        dedupe_key=f"email_action:{event_id}",
        timestamp=timestamp,
    )
    if execution_status == EMAIL_ACTION_EXECUTION_FAILED:
        record_infonalia_activity(
            conn,
            category="download_ai",
            event_type="nuria_action_failed",
            source="email_action",
            actor=sender_email,
            result="error",
            title="Falló una orden de Nuria",
            detail=failure_detail or message,
            day_id=review_id,
            licitacion_id=licitacion_id,
            severity=SEVERITY_CRITICAL,
            metadata={
                "email_action_event_id": event_id,
                "download_job_id": download_job_id or None,
                "action_code": action_code,
                "failure_stage": failure_stage,
                "failure_code": failure_code,
            },
            dedupe_key=f"email_action:{event_id}:failed",
            timestamp=timestamp,
        )
    ai_summary_request_id = 0
    if action_code == ACTION_AI_SUMMARY:
        ai_summary_request_id = _create_email_ai_summary_request(
            conn,
            event_id=event_id,
            review_id=review_id,
            licitacion_id=licitacion_id,
            download_request=download_request,
            source_message_id=source_message_id,
            sender_email=sender_email,
            timestamp=timestamp,
        )
    if (
        action_code in EMAIL_ACTION_DOWNLOAD_CODES
        and isinstance(queue_info, Mapping)
        and clean_text(queue_info.get("status")) == "queued"
        and queue_info.get("job_id")
    ):
        # El trabajo y su evento deben ser visibles desde la conexión independiente
        # del worker antes de crear el proceso. De otro modo el worker puede arrancar,
        # no encontrar el trabajo todavía no confirmado y terminar silenciosamente.
        conn.commit()
        worker_failure_detail = ""
        try:
            try:
                from . import app as app_module
            except ImportError:
                import app as app_module  # type: ignore

            worker_info = app_module.start_download_worker(job_id=int(queue_info["job_id"]))
            download_request["worker"] = worker_info
            if isinstance(worker_info, Mapping) and worker_info.get("started") is False:
                worker_failure_detail = clean_text(worker_info.get("error")) or "No se pudo iniciar el proceso de descarga."
        except Exception as exc:
            worker_failure_detail = clean_text(exc) or exc.__class__.__name__
        if worker_failure_detail:
            message += f" Worker de descarga no iniciado automáticamente: {worker_failure_detail}."
            conn.execute(
                """
                UPDATE email_action_events
                SET reason = ?, execution_status = ?, failure_stage = 'worker_start',
                    failure_code = 'DOWNLOAD_WORKER_START_FAILED', failure_detail = ?,
                    telegram_notification_status = 'pending',
                    telegram_notification_next_attempt_at = NULL,
                    telegram_notification_claimed_at = NULL
                WHERE id = ?
                """,
                (
                    message,
                    EMAIL_ACTION_EXECUTION_FAILED,
                    worker_failure_detail[:2000],
                    event_id,
                ),
            )
            conn.execute(
                """
                UPDATE download_jobs
                SET status = 'failed', error_message = ?, finished_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'running')
                """,
                (worker_failure_detail[:2000], timestamp, timestamp, int(queue_info["job_id"])),
            )
            record_infonalia_activity(
                conn,
                category="download_ai",
                event_type="nuria_action_failed",
                source="email_action",
                actor=sender_email,
                result="error",
                title="Falló una orden de Nuria",
                detail=worker_failure_detail,
                day_id=review_id,
                licitacion_id=licitacion_id,
                severity=SEVERITY_CRITICAL,
                metadata={
                    "email_action_event_id": event_id,
                    "download_job_id": int(queue_info["job_id"]),
                    "action_code": action_code,
                    "failure_stage": "worker_start",
                    "failure_code": "DOWNLOAD_WORKER_START_FAILED",
                },
                dedupe_key=f"email_action:{event_id}:failed",
                timestamp=timestamp,
            )
    return {
        "status": "processed",
        "action": action["name"],
        "action_code": action_code,
        "review_id": review_id,
        "review_date": clean_text(day["fecha"]),
        "licitacion_id": licitacion_id,
        "expediente": clean_text(licitacion["expediente"]),
        "organismo": clean_text(licitacion["organismo"]),
        "sender_email": clean_text(sender_email).lower(),
        "processed_at": timestamp,
        "review_was_closed": review_was_closed,
        "old_state": old_state,
        "new_state": new_state,
        "changed": changed,
        "download_request": download_request,
        "ai_summary_request_id": ai_summary_request_id or None,
        "message": message,
    }


def build_late_decision_notification_email(result: Mapping[str, object]) -> tuple[str, str, str]:
    expediente = clean_text(result.get("expediente")) or f"Licitación {result.get('licitacion_id')}"
    organismo = clean_text(result.get("organismo")) or "Sin organismo informado"
    review_date = clean_text(result.get("review_date"))
    old_state = clean_text(result.get("old_state"))
    new_state = clean_text(result.get("new_state"))
    action = clean_text(result.get("action"))
    sender = clean_text(result.get("sender_email"))
    processed_at = clean_text(result.get("processed_at"))
    operation = clean_text(result.get("message"))
    subject = f"Cambio de decisión de Nuria tras cierre · {expediente}"
    body = "\n".join(
        [
            "Se ha procesado una nueva decisión de Nuria después del cierre del Día Infonalia.",
            "",
            f"Día Infonalia: {format_date_es(review_date) if review_date else 'Sin fecha'}",
            f"Expediente: {expediente}",
            f"Organismo: {organismo}",
            f"Acción recibida: {action}",
            f"Estado anterior: {old_state}",
            f"Estado nuevo: {new_state}",
            f"Remitente: {sender}",
            f"Procesada: {processed_at}",
            "",
            operation,
            "",
            "El Día Infonalia permanece cerrado.",
        ]
    )
    rows = [
        ("Día Infonalia", format_date_es(review_date) if review_date else "Sin fecha"),
        ("Expediente", expediente),
        ("Organismo", organismo),
        ("Acción recibida", action),
        ("Estado anterior", old_state),
        ("Estado nuevo", new_state),
        ("Remitente", sender),
        ("Procesada", processed_at),
    ]
    html_rows = "".join(
        "<tr>"
        f"<td style='padding:9px 12px; color:#667085; font-weight:800;'>{html.escape(label)}</td>"
        f"<td style='padding:9px 12px;'>{html.escape(value)}</td>"
        "</tr>"
        for label, value in rows
    )
    html_body = build_llangon_email_shell(
        eyebrow="Incidencia Infonalia",
        title="Cambio de decisión posterior al cierre",
        subtitle=expediente,
        body_html=(
            "<div style='padding:12px 14px; margin-bottom:14px; background:#fff0f0; "
            "border:1px solid #ef9a9a; border-radius:8px; color:#9b1c1c; font-weight:800;'>"
            "La última decisión válida de Nuria se ha aplicado y el día permanece cerrado."
            "</div>"
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; "
            "border:1px solid #d9e2ec;'>"
            f"{html_rows}</table>"
            f"<p style='margin:14px 0 0 0;'>{html.escape(operation)}</p>"
        ),
        closing_html="Revisa este cambio en el Histórico general de Días Infonalia.",
    )
    return subject, body, html_body


def build_review_confirmation_email(result: Mapping[str, object]) -> tuple[str, str, str]:
    review_date = clean_text(result.get("review_date"))
    subject = f"Revisión Infonalia completada: {review_date or 'sin fecha'}"
    body = "\n".join(
        [
            f"Revisión marcada como revisada: {review_date or 'sin fecha'}",
            f"ID revisión: {result.get('review_id')}",
            f"Total licitaciones incluidas: {result.get('total_items')}",
            f"Acciones individuales recibidas: {result.get('individual_actions')}",
            f"Descartadas automáticamente: {result.get('auto_discarded')}",
            f"Sin cambios: {result.get('untouched')}",
        ]
    )
    html_body = build_llangon_email_shell(
        eyebrow="Llangón Web App",
        title="Revisión Infonalia completada",
        subtitle=review_date,
        body_html=(
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; border:1px solid #d9e2ec;'>"
            f"<tr><td style='padding:10px 12px; color:#667085; font-weight:800;'>Total licitaciones incluidas</td><td align='right' style='padding:10px 12px;'>{html.escape(str(result.get('total_items')))}</td></tr>"
            f"<tr><td style='padding:10px 12px; color:#667085; font-weight:800;'>Acciones individuales recibidas</td><td align='right' style='padding:10px 12px;'>{html.escape(str(result.get('individual_actions')))}</td></tr>"
            f"<tr><td style='padding:10px 12px; color:#667085; font-weight:800;'>Descartadas automáticamente</td><td align='right' style='padding:10px 12px;'>{html.escape(str(result.get('auto_discarded')))}</td></tr>"
            f"<tr><td style='padding:10px 12px; color:#667085; font-weight:800;'>Sin cambios</td><td align='right' style='padding:10px 12px;'>{html.escape(str(result.get('untouched')))}</td></tr>"
            "</table>"
        ),
        closing_html="Confirmación generada tras recibir la orden Revisado por correo.",
    )
    return subject, body, html_body


def _process_review_action(
    conn: sqlite3.Connection,
    *,
    code: str,
    review_id: int,
    sender_email: str,
    source_message_id: str,
    subject: str,
    timestamp: str,
    confirmation_sender: Callable[[str, str, str], None] | None = None,
) -> dict[str, object]:
    day = conn.execute("SELECT * FROM infonalia_dias WHERE id = ?", (review_id,)).fetchone()
    if not day:
        error = "Revisión Infonalia no encontrada."
        _insert_email_action_event(
            conn,
            created_at=timestamp,
            source_message_id=source_message_id,
            from_email=sender_email,
            subject=subject,
            code=code,
            action_code=ACTION_REVIEWED,
            action_name=ACTION_DEFINITIONS[ACTION_REVIEWED]["name"],
            review_id=review_id,
            result="error",
            reason=error,
        )
        return {"status": "error", "error_code": "REVIEW_NOT_FOUND", "message": error}
    if not _review_is_open(day):
        message = "Orden ignorada: revisión Infonalia ya cerrada."
        _insert_email_action_event(
            conn,
            created_at=timestamp,
            source_message_id=source_message_id,
            from_email=sender_email,
            subject=subject,
            code=code,
            action_code=ACTION_REVIEWED,
            action_name=ACTION_DEFINITIONS[ACTION_REVIEWED]["name"],
            review_id=review_id,
            result="ignored",
            reason=message,
        )
        return {"status": "ignored", "error_code": "REVIEW_CLOSED", "message": message}

    rows = conn.execute("SELECT * FROM licitaciones WHERE infonalia_dia_id = ? ORDER BY id ASC", (review_id,)).fetchall()
    processed_actions = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM email_action_events
        WHERE review_id = ?
          AND action_code IN (?, ?, ?, ?)
          AND result = 'processed'
        """,
        (review_id, ACTION_DISCARD, ACTION_DOWNLOAD_REVIEW, ACTION_PREPARE, ACTION_AI_SUMMARY),
    ).fetchone()["total"]
    auto_discarded = 0
    untouched = 0
    for licitacion in rows:
        old_state = _normalize_state_for_email_action(licitacion["estado"])
        if old_state in REVIEW_UNDECIDED_STATES:
            conn.execute(
                "UPDATE licitaciones SET estado = ?, updated_at = ? WHERE id = ?",
                (ESTADO_DESCARTADA, timestamp, int(licitacion["id"])),
            )
            record_licitacion_history(
                conn,
                int(licitacion["id"]),
                event_type="estado",
                old_value=old_state,
                new_value=ESTADO_DESCARTADA,
                user_id=sender_email,
                timestamp=timestamp,
            )
            create_system_comment(
                conn,
                entity_type="licitacion",
                entity_id=int(licitacion["id"]),
                body=(
                    "Descartada automáticamente al marcar como revisada la revisión "
                    f"Infonalia del {format_date_es(day['fecha'])}, sin acción individual asignada desde el correo."
                ),
                metadata={"event_type": "email_action_reviewed", "code": code},
                timestamp=timestamp,
            )
            auto_discarded += 1
        else:
            untouched += 1

    conn.execute(
        """
        UPDATE infonalia_dias
        SET reviewed_at = ?,
            nuria_dirty_at = NULL,
            estado = 'Completado',
            updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, review_id),
    )
    message = f"Revisión {review_id} marcada como revisada."
    event_id = _insert_email_action_event(
        conn,
        created_at=timestamp,
        source_message_id=source_message_id,
        from_email=sender_email,
        subject=subject,
        code=code,
        action_code=ACTION_REVIEWED,
        action_name=ACTION_DEFINITIONS[ACTION_REVIEWED]["name"],
        review_id=review_id,
        result="processed",
        reason=message,
    )
    record_infonalia_activity(
        conn,
        category="closure",
        event_type="day_reviewed_by_email",
        source="email",
        actor=sender_email,
        result="processed",
        title="Día Infonalia cerrado por orden de Nuria",
        detail=(
            f"Descartadas automáticamente: {auto_discarded}. "
            f"Sin cambios: {untouched}."
        ),
        day_id=review_id,
        severity=SEVERITY_NORMAL,
        metadata={"email_action_event_id": event_id, "source_message_id": source_message_id},
        dedupe_key=f"email_action:{event_id}",
        timestamp=timestamp,
    )
    result = {
        "status": "processed",
        "action": ACTION_DEFINITIONS[ACTION_REVIEWED]["name"],
        "review_id": review_id,
        "review_date": format_date_es(day["fecha"]),
        "total_items": len(rows),
        "individual_actions": int(processed_actions or 0),
        "auto_discarded": auto_discarded,
        "untouched": untouched,
        "message": message,
    }
    if confirmation_sender:
        subject, body, html_body = build_review_confirmation_email(result)
        confirmation_sender(subject, body, html_body)
    return result


def process_email_action(
    conn: sqlite3.Connection,
    *,
    code: str,
    sender_email: str,
    source_message_id: str = "",
    subject: str = "",
    allowed_senders: Sequence[str] | str | None = None,
    timestamp: str | None = None,
    confirmation_sender: Callable[[str, str, str], None] | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    ensure_email_action_schema(conn)
    processed_at = timestamp or now_iso()
    normalized_code = clean_text(code)
    parsed = parse_action_code(normalized_code)
    action_code = clean_text(parsed.get("action_code"))
    action = ACTION_DEFINITIONS.get(action_code)
    entity_id = int(parsed.get("entity_id") or 0)
    code_row = action_code_row(conn, normalized_code)

    def audit_blocked(*, result: str, reason: str, review_id: int | None = None, licitacion_id: int | None = None, previous_status: str = "", new_status: str = "") -> None:
        if dry_run:
            return
        event_id = _insert_email_action_event(
            conn,
            created_at=processed_at,
            source_message_id=source_message_id,
            from_email=sender_email,
            subject=subject,
            code=normalized_code,
            action_code=action_code,
            action_name=(action or {}).get("name", ""),
            review_id=review_id,
            licitacion_id=licitacion_id,
            previous_status=previous_status,
            new_status=new_status,
            result=result,
            reason=reason,
        )
        record_infonalia_activity(
            conn,
            category="nuria_action",
            event_type=f"email_action_{clean_text(result) or 'blocked'}",
            source="email",
            actor=sender_email,
            result=result,
            title=(
                "Error en una orden de Nuria"
                if result == "error"
                else "Orden de Nuria ignorada"
            ),
            detail=reason,
            day_id=review_id,
            licitacion_id=licitacion_id,
            old_value=previous_status,
            new_value=new_status or previous_status,
            severity=SEVERITY_CRITICAL if result == "error" else SEVERITY_ATTENTION,
            metadata={
                "email_action_event_id": event_id,
                "action_code": action_code,
                "source_message_id": clean_text(source_message_id),
            },
            dedupe_key=(
                f"email_action_blocked:{clean_text(source_message_id) or normalized_code}:"
                f"{normalized_code}:{clean_text(result)}"
            ),
            timestamp=processed_at,
        )

    if not parsed["well_formed"]:
        message = "Código de acción no válido."
        audit_blocked(result="error", reason=message)
        return {"status": "error", "error_code": "INVALID_CODE", "message": message}
    if not action:
        message = "Acción no reconocida."
        audit_blocked(result="error", reason=message)
        return {"status": "error", "error_code": "UNKNOWN_ACTION", "message": message}
    blocked_review_id = entity_id if action_code == ACTION_REVIEWED else None
    blocked_licitacion_id = entity_id if action_code != ACTION_REVIEWED else None
    blocked_state = ""
    if blocked_licitacion_id:
        blocked_row = conn.execute(
            "SELECT infonalia_dia_id, estado FROM licitaciones WHERE id = ?",
            (blocked_licitacion_id,),
        ).fetchone()
        if blocked_row:
            blocked_review_id = int(blocked_row["infonalia_dia_id"] or 0) or None
            blocked_state = clean_text(blocked_row["estado"])
    if not split_emails(allowed_senders or ""):
        message = "Sin remitentes autorizados configurados."
        audit_blocked(
            result="error",
            reason=message,
            review_id=blocked_review_id,
            licitacion_id=blocked_licitacion_id,
            previous_status=blocked_state,
            new_status=blocked_state,
        )
        return {
            "status": "error",
            "error_code": "NO_ALLOWED_SENDERS",
            "message": message,
        }
    if not sender_is_allowed(sender_email, allowed_senders):
        error = "Remitente no autorizado."
        audit_blocked(
            result="error",
            reason=error,
            review_id=blocked_review_id,
            licitacion_id=blocked_licitacion_id,
            previous_status=blocked_state,
            new_status=blocked_state,
        )
        return {"status": "error", "error_code": "UNAUTHORIZED_SENDER", "message": error}
    if action_code == ACTION_AI_SUMMARY and not review_ai_summary_button_enabled():
        message = "Orden ignorada: el resumen IA por correo está desactivado."
        audit_blocked(result="ignored", reason=message)
        return {"status": "ignored", "error_code": "AI_SUMMARY_DISABLED", "message": message}

    if _same_message_already_processed(conn, code_row=code_row, source_message_id=source_message_id):
        message = "Orden duplicada ignorada: este correo ya fue procesado."
        duplicate_state = ""
        review_id = None
        licitacion_id = None
        if code_row:
            review_id = int(code_row["review_id"] or 0) or None
            licitacion_id = int(code_row["licitacion_id"] or 0) or None
        if licitacion_id:
            licitacion = conn.execute("SELECT estado FROM licitaciones WHERE id = ?", (licitacion_id,)).fetchone()
            if licitacion:
                duplicate_state = clean_text(licitacion["estado"])
        audit_blocked(
            result="ignored",
            reason=message,
            review_id=review_id,
            licitacion_id=licitacion_id,
            previous_status=duplicate_state,
            new_status=duplicate_state,
        )
        return {
            "status": "ignored",
            "error_code": "DUPLICATE_EMAIL_ACTION",
            "message": message,
            "licitacion_id": licitacion_id,
            "review_id": review_id,
            "duplicate_source": "action_code",
        }

    duplicate_event = _processed_email_action_event(
        conn,
        code=normalized_code,
        source_message_id=source_message_id,
    )
    if duplicate_event:
        message = "Orden duplicada ignorada: este correo ya fue procesado."
        review_id = int(duplicate_event["review_id"] or 0) or None
        licitacion_id = int(duplicate_event["licitacion_id"] or 0) or None
        previous_status = clean_text(duplicate_event["new_status"] or duplicate_event["previous_status"])
        audit_blocked(
            result="ignored",
            reason=message,
            review_id=review_id,
            licitacion_id=licitacion_id,
            previous_status=previous_status,
            new_status=previous_status,
        )
        return {
            "status": "ignored",
            "error_code": "DUPLICATE_EMAIL_ACTION",
            "message": message,
            "duplicate_event_id": int(duplicate_event["id"]),
            "licitacion_id": licitacion_id,
            "review_id": review_id,
        }

    check = check_action_code(
        conn,
        code=normalized_code,
        sender_email=sender_email,
        allowed_senders=allowed_senders,
    )
    if not check.get("processable"):
        reason = clean_text(check.get("reason")) or "orden no procesable"
        review_id = int(check.get("review_id") or 0) or None
        licitacion_id = int(check.get("licitacion_id") or 0) or None
        previous_status = clean_text(check.get("licitacion_status"))
        if reason == "revisión Infonalia ya cerrada":
            message = "Orden ignorada: revisión Infonalia ya cerrada."
            audit_blocked(
                result="ignored",
                reason=message,
                review_id=review_id,
                licitacion_id=licitacion_id,
                previous_status=previous_status,
                new_status=previous_status,
            )
            return {"status": "ignored", "error_code": "REVIEW_CLOSED", "message": message}
        if reason == "estado avanzado no modificable desde correo":
            message = "Orden ignorada: la licitación está en estado avanzado y no puede modificarse desde correo de revisión."
            audit_blocked(
                result="ignored",
                reason=message,
                review_id=review_id,
                licitacion_id=licitacion_id,
                previous_status=previous_status,
                new_status=previous_status,
            )
            return {"status": "ignored", "error_code": "ADVANCED_STATE", "message": message}
        if reason == "resumen IA por correo desactivado":
            message = "Orden ignorada: el resumen IA por correo está desactivado."
            audit_blocked(
                result="ignored",
                reason=message,
                review_id=review_id,
                licitacion_id=licitacion_id,
                previous_status=previous_status,
                new_status=previous_status,
            )
            return {"status": "ignored", "error_code": "AI_SUMMARY_DISABLED", "message": message}
        error_codes = {
            "licitación inexistente": "LICITACION_NOT_FOUND",
            "revisión inexistente": "REVIEW_NOT_FOUND",
            "licitación sin revisión Infonalia asociada": "NO_REVIEW_LINK",
        }
        audit_blocked(
            result="error",
            reason=reason,
            review_id=review_id,
            licitacion_id=licitacion_id,
            previous_status=previous_status,
        )
        return {"status": "error", "error_code": error_codes.get(reason, "NOT_PROCESSABLE"), "message": reason}

    if dry_run and action_code in ACTION_DEFINITIONS:
        old_state = clean_text(check.get("licitacion_status"))
        new_state = ACTION_DEFINITIONS[action_code]["state"] if action_code != ACTION_REVIEWED else ""
        return {
            "status": "dry_run",
            "would_process": True,
            "action": ACTION_DEFINITIONS[action_code]["name"],
            "action_code": action_code,
            "licitacion_id": check.get("licitacion_id"),
            "review_id": check.get("review_id"),
            "old_state": old_state,
            "new_state": new_state,
            "would_change": bool(old_state and new_state and old_state != new_state),
            "message": "Dry-run: la acción se validó, pero no se ha ejecutado.",
        }
    if action_code == ACTION_REVIEWED:
        result = _process_review_action(
            conn,
            code=normalized_code,
            review_id=entity_id,
            sender_email=sender_email,
            source_message_id=source_message_id,
            subject=subject,
            timestamp=processed_at,
            confirmation_sender=confirmation_sender,
        )
        if result.get("status") == "processed" and code_row:
            _mark_action(
                conn,
                int(code_row["id"]),
                status="processed",
                timestamp=processed_at,
                sender_email=sender_email,
                source_message_id=source_message_id,
                result_message=clean_text(result.get("message")),
            )
        return result
    if action_code in ACTION_DEFINITIONS:
        result = _process_individual_action(
            conn,
            code=normalized_code,
            action_code=action_code,
            licitacion_id=entity_id,
            sender_email=sender_email,
            source_message_id=source_message_id,
            subject=subject,
            timestamp=processed_at,
        )
        if result.get("status") == "processed" and code_row:
            _mark_action(
                conn,
                int(code_row["id"]),
                status="processed",
                timestamp=processed_at,
                sender_email=sender_email,
                source_message_id=source_message_id,
                result_message=clean_text(result.get("message")),
            )
        return result
    message = "Acción no reconocida."
    audit_blocked(result="error", reason=message)
    return {"status": "error", "error_code": "UNKNOWN_ACTION", "message": message}
