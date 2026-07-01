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
    from .infonalia_days import refresh_day_status
    from .licitacion_center import record_licitacion_history
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
    from infonalia_days import refresh_day_status
    from licitacion_center import record_licitacion_history
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
ACTION_REVIEWED = "99"

ACTION_MAILBOX_TO_DEFAULT = "info3llangon@gmail.com"
ACTION_MAILBOX_CC_DEFAULT = "info3@llangon.com"
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


def split_emails(value: object) -> list[str]:
    result: list[str] = []
    if isinstance(value, (list, tuple, set)):
        source = []
        for item in value:
            source.extend(re.split(r"[;,]", clean_text(item)))
    else:
        source = re.split(r"[;,]", clean_text(value))
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
            reason TEXT
        )
        """
    )
    additions = {
        "processed_at": "TEXT",
        "processed_by_email": "TEXT",
        "source_message_id": "TEXT",
        "result_message": "TEXT",
        "error_message": "TEXT",
    }
    existing = {row[1] for row in conn.execute("PRAGMA table_info(email_action_codes)").fetchall()}
    for column, definition in additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE email_action_codes ADD COLUMN {column} {definition}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_email_action_codes_code ON email_action_codes(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_codes_review ON email_action_codes(review_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_codes_licitacion ON email_action_codes(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_codes_status ON email_action_codes(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_code ON email_action_events(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_review ON email_action_events(review_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_licitacion ON email_action_events(licitacion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_action_events_created ON email_action_events(created_at)")


def ensure_review_action_codes(
    conn: sqlite3.Connection,
    *,
    review_id: int,
    licitaciones: Sequence[sqlite3.Row | Mapping[str, object]],
    timestamp: str | None = None,
) -> dict[tuple[int | None, str], str]:
    ensure_email_action_schema(conn)
    created_at = timestamp or now_iso()
    result: dict[tuple[int | None, str], str] = {}

    for row in licitaciones:
        licitacion_id = int(row["id"])
        for action_code in (ACTION_DISCARD, ACTION_DOWNLOAD_REVIEW, ACTION_PREPARE):
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
    time_label = parse_time_value(_row_value(row, "hora_limite")) or "Sin hora"
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
) -> str:
    generated_at = generated_at or datetime.now().replace(microsecond=0)
    rows = sorted(
        licitaciones,
        key=lambda row: (
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
    for row in rows:
        licitacion_id = int(row["id"])
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
        links = (
            _link_html(_row_value(row, "enlace_perfil"), "Perfil del contratante")
            + _link_html(_row_value(row, "enlace_infonalia"), "Anuncio Infonalia")
        )
        buttons = []
        for action_code, color, bg in (
            (ACTION_DISCARD, "#991b1b", "#fee2e2"),
            (ACTION_DOWNLOAD_REVIEW, "#0f5b8d", "#e8f7ff"),
            (ACTION_PREPARE, "#0e7f15", "#e7f8ea"),
        ):
            href = _mailto(
                mailbox_to,
                build_licitacion_action_subject(row, action_code),
                build_licitacion_action_body(row, review_id=int(day["id"]), review_date=fecha, action_code=action_code),
                cc=mailbox_cc,
            )
            buttons.append(_button_html(href, ACTION_DEFINITIONS[action_code]["name"], color=color, background=bg))

        cards.append(
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
    body_html = intro + "".join(cards) + reviewed_button
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
) -> None:
    ensure_email_action_schema(conn)
    conn.execute(
        """
        INSERT INTO email_action_events (
            created_at, source_message_id, from_email, subject, code, action_code,
            action_name, review_id, licitacion_id, previous_status, new_status,
            result, reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            clean_text(result),
            clean_text(reason),
        ),
    )


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
    }
    if not parsed["well_formed"]:
        return payload
    action_code = clean_text(parsed["action_code"])
    action = ACTION_DEFINITIONS.get(action_code)
    if not action:
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
    payload["review_status"] = "abierta" if _review_is_open(day) else "revisada"
    if not _review_is_open(day):
        payload["reason"] = "revisión Infonalia ya cerrada"
        return payload
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
    payload["reason"] = "revisión abierta y licitación procesable"
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
    if not _review_is_open(day):
        message = "Orden ignorada: revisión Infonalia ya cerrada."
        _insert_email_action_event(
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
            result="ignored",
            reason=message,
        )
        return {"status": "ignored", "error_code": "REVIEW_CLOSED", "message": message}
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
    message = f"Acción {action['name']} aplicada a la licitación {licitacion_id}."
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
        new_status=new_state,
        result="processed",
        reason=message,
    )
    return {
        "status": "processed",
        "action": action["name"],
        "licitacion_id": licitacion_id,
        "old_state": old_state,
        "new_state": new_state,
        "changed": changed,
        "message": message,
    }


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
          AND action_code IN (?, ?, ?)
          AND result = 'processed'
        """,
        (review_id, ACTION_DISCARD, ACTION_DOWNLOAD_REVIEW, ACTION_PREPARE),
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
        result="processed",
        reason=message,
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

    def audit_blocked(*, result: str, reason: str, review_id: int | None = None, licitacion_id: int | None = None, previous_status: str = "", new_status: str = "") -> None:
        if dry_run:
            return
        _insert_email_action_event(
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

    if not parsed["well_formed"]:
        message = "Código de acción no válido."
        audit_blocked(result="error", reason=message)
        return {"status": "error", "error_code": "INVALID_CODE", "message": message}
    if not action:
        message = "Acción no reconocida."
        audit_blocked(result="error", reason=message)
        return {"status": "error", "error_code": "UNKNOWN_ACTION", "message": message}
    if not split_emails(allowed_senders or ""):
        message = "Sin remitentes autorizados configurados."
        audit_blocked(result="error", reason=message)
        return {
            "status": "error",
            "error_code": "NO_ALLOWED_SENDERS",
            "message": message,
        }
    if not sender_is_allowed(sender_email, allowed_senders):
        error = "Remitente no autorizado."
        audit_blocked(result="error", reason=error)
        return {"status": "error", "error_code": "UNAUTHORIZED_SENDER", "message": error}

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
        return _process_review_action(
            conn,
            code=normalized_code,
            review_id=entity_id,
            sender_email=sender_email,
            source_message_id=source_message_id,
            subject=subject,
            timestamp=processed_at,
            confirmation_sender=confirmation_sender,
        )
    if action_code in ACTION_DEFINITIONS:
        return _process_individual_action(
            conn,
            code=normalized_code,
            action_code=action_code,
            licitacion_id=entity_id,
            sender_email=sender_email,
            source_message_id=source_message_id,
            subject=subject,
            timestamp=processed_at,
        )
    message = "Acción no reconocida."
    audit_blocked(result="error", reason=message)
    return {"status": "error", "error_code": "UNKNOWN_ACTION", "message": message}
