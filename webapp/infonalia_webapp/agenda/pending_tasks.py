from __future__ import annotations

import sqlite3
import unicodedata
from datetime import datetime

try:
    from ..clientes_envios import CLIENTE_ENVIO_PANEL_TITLES, CLIENTE_ENVIO_PENDIENTES_AGENDA, list_cliente_envios
    from ..licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_PREPARADA,
        ESTADO_PREPARAR_FICHA,
        ESTADOS_ORDEN,
    )
    from ..normalization import clean_text
    from .service import (
        _actuacion_licitaciones,
        agenda_datetime_from_date_time,
        agenda_parse_datetime,
    )
except ImportError:
    from clientes_envios import CLIENTE_ENVIO_PANEL_TITLES, CLIENTE_ENVIO_PENDIENTES_AGENDA, list_cliente_envios
    from licitacion_states import (
        ESTADO_DESCARGAR_PARA_VER,
        ESTADO_PREPARADA,
        ESTADO_PREPARAR_FICHA,
        ESTADOS_ORDEN,
    )
    from normalization import clean_text
    from agenda.service import (
        _actuacion_licitaciones,
        agenda_datetime_from_date_time,
        agenda_parse_datetime,
    )


PENDING_LICITACION_STATES = {
    ESTADO_DESCARGAR_PARA_VER,
    ESTADO_PREPARAR_FICHA,
    ESTADO_PREPARADA,
}

TASK_STATE_OPTIONS = [
    {"value": "pendiente", "label": "Pendiente"},
    {"value": "en_preparacion", "label": "En preparación"},
    {"value": "preparado", "label": "Preparado"},
    {"value": "enviado", "label": "Enviado"},
    {"value": "cancelado", "label": "Cancelado"},
]


def _state_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value).lower())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return "".join(character for character in text if character.isalnum())


def task_state_label(value: object) -> str:
    return {
        "pendiente": "Pendiente",
        "encurso": "Pendiente",
        "enpreparacion": "En preparación",
        "preparado": "Preparado",
        "preparada": "Preparado",
        "respondida": "Enviado",
        "cerrado": "Enviado",
        "cerrada": "Enviado",
        "enviado": "Enviado",
        "enviada": "Enviado",
        "cancelado": "Cancelado",
        "cancelada": "Cancelado",
    }.get(_state_key(value), "Pendiente")


def is_pending_task_state(value: object) -> bool:
    return task_state_label(value) in {"Pendiente", "En preparación", "Preparado"}


def task_state_value(value: object) -> str:
    label = task_state_label(value)
    return {
        "Pendiente": "pendiente",
        "En preparación": "en_preparacion",
        "Preparado": "preparado",
        "Enviado": "enviado",
        "Cancelado": "cancelado",
    }.get(label, "pendiente")


def _event_parts(event_dt: datetime | None, *, current: datetime) -> dict[str, object]:
    return {
        "date": event_dt.date().isoformat() if event_dt else "",
        "datetime": event_dt.replace(microsecond=0).isoformat() if event_dt else "",
        "is_overdue": bool(event_dt and event_dt < current),
        "is_without_date": event_dt is None,
        "is_today": bool(event_dt and event_dt.date() == current.date()),
        "color_type": "vencido" if event_dt and event_dt < current else "",
    }


def _task_sort_key(item: dict[str, object]) -> tuple[object, ...]:
    if item.get("is_overdue"):
        bucket = 0
    elif item.get("is_without_date"):
        bucket = 1
    elif item.get("is_today"):
        bucket = 2
    else:
        bucket = 3
    return (
        bucket,
        item.get("datetime") or "9999-12-31T23:59:59",
        clean_text(item.get("title")).lower(),
        item.get("source_id") or 0,
    )


def _groups(items: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    return {
        "overdue": [item for item in items if item.get("is_overdue")],
        "no_date": [item for item in items if item.get("is_without_date")],
        "today": [item for item in items if item.get("is_today") and not item.get("is_overdue")],
        "upcoming": [
            item for item in items
            if not item.get("is_overdue") and not item.get("is_without_date") and not item.get("is_today")
        ],
    }


def _matches_query(item: dict[str, object], query: str) -> bool:
    q = query.lower().strip()
    if not q:
        return True
    values = [
        item.get("title"),
        item.get("subtitle"),
        item.get("description"),
        item.get("state"),
        item.get("expediente"),
        item.get("provincia"),
        item.get("cliente_nombre"),
        item.get("destinatario_email"),
    ]
    for licitacion in item.get("linked_licitaciones") or []:
        values.extend(
            licitacion.get(key)
            for key in ("expediente", "organismo", "objeto", "plataforma", "provincia", "estado")
        )
    return any(q in clean_text(value).lower() for value in values)


def _cliente_envio_panel_key(state_value: object) -> str:
    state = clean_text(state_value)
    if state == "listo_para_preparar_correo":
        return "ready"
    if state == "correo_outlook_generado":
        return "generated"
    return "incidents"


def _licitacion_tasks(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    placeholders = ",".join("?" for _ in PENDING_LICITACION_STATES)
    rows = conn.execute(
        f"""
        SELECT
            id, expediente, objeto, organismo, tipo, presupuesto, fecha_limite, hora_limite,
            estado, provincia, plataforma, enlace_perfil, enlace_infonalia, ruta_carpeta
        FROM licitaciones
        WHERE estado IN ({placeholders})
          AND COALESCE(tipo_publicacion, 'licitacion') = 'licitacion'
        """,
        sorted(PENDING_LICITACION_STATES),
    ).fetchall()
    items = []
    for row in rows:
        event_dt = agenda_datetime_from_date_time(row["fecha_limite"], row["hora_limite"])
        title = row["expediente"] or f"Licitación {row['id']}"
        linked = [{
            "id": row["id"],
            "expediente": row["expediente"] or "",
            "organismo": row["organismo"] or "",
            "objeto": row["objeto"] or "",
            "tipo": row["tipo"] or "",
            "presupuesto": row["presupuesto"],
            "fecha_limite": row["fecha_limite"] or "",
            "hora_limite": row["hora_limite"] or "",
            "estado": row["estado"] or "",
            "provincia": row["provincia"] or "",
            "plataforma": row["plataforma"] or "",
            "enlace_perfil": row["enlace_perfil"] or "",
            "enlace_infonalia": row["enlace_infonalia"] or "",
            "ruta_carpeta": row["ruta_carpeta"] or "",
        }]
        items.append({
            "id": f"licitacion:{row['id']}",
            "type": "licitacion",
            "source_type": "licitacion",
            "source_id": int(row["id"]),
            "title": title,
            "subtitle": row["objeto"] or row["organismo"] or "Licitación sin detalle",
            "description": row["organismo"] or "",
            "status": row["estado"] or "",
            "state": row["estado"] or "",
            "state_value": row["estado"] or "",
            "expediente": row["expediente"] or "",
            "organismo": row["organismo"] or "",
            "objeto": row["objeto"] or "",
            "tipo": row["tipo"] or "",
            "presupuesto": row["presupuesto"],
            "fecha_limite": row["fecha_limite"] or "",
            "hora_limite": row["hora_limite"] or "",
            "provincia": row["provincia"] or "",
            "plataforma": row["plataforma"] or "",
            "enlace_perfil": row["enlace_perfil"] or "",
            "enlace_infonalia": row["enlace_infonalia"] or "",
            "ruta_carpeta": row["ruta_carpeta"] or "",
            "linked_licitaciones": linked,
            "state_options": [{"value": state, "label": state} for state in ESTADOS_ORDEN],
            **_event_parts(event_dt, current=current),
        })
    return items


def _actuacion_tasks(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, titulo, descripcion, estado, deadline_at, tipo, origen
        FROM actuaciones
        ORDER BY deadline_at ASC, id ASC
        """
    ).fetchall()
    items = []
    for row in rows:
        state = task_state_label(row["estado"])
        if state not in {"Pendiente", "En preparación", "Preparado"}:
            continue
        linked = _actuacion_licitaciones(conn, int(row["id"]))
        event_dt = agenda_parse_datetime(row["deadline_at"])
        items.append({
            "id": f"actuacion:{row['id']}",
            "type": "actuacion",
            "source_type": "actuacion",
            "source_id": int(row["id"]),
            "title": row["titulo"],
            "subtitle": row["descripcion"] or "Actuación sin descripción",
            "description": row["descripcion"] or "",
            "status": state,
            "state": state,
            "state_value": task_state_value(row["estado"]),
            "raw_state": row["estado"] or "",
            "linked_licitaciones": linked,
            "state_options": TASK_STATE_OPTIONS,
            **_event_parts(event_dt, current=current),
        })
    return items


def _internal_event_tasks(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, titulo, descripcion, starts_at, estado
        FROM agenda_eventos
        ORDER BY starts_at ASC, id ASC
        """
    ).fetchall()
    items = []
    for row in rows:
        state = task_state_label(row["estado"])
        if state not in {"Pendiente", "En preparación", "Preparado"}:
            continue
        event_dt = agenda_parse_datetime(row["starts_at"])
        items.append({
            "id": f"interno:{row['id']}",
            "type": "interno",
            "source_type": "interno",
            "source_id": int(row["id"]),
            "title": row["titulo"],
            "subtitle": row["descripcion"] or "Evento interno",
            "description": row["descripcion"] or "",
            "status": state,
            "state": state,
            "state_value": task_state_value(row["estado"]),
            "raw_state": row["estado"] or "",
            "state_options": TASK_STATE_OPTIONS,
            **_event_parts(event_dt, current=current),
        })
    return items


def _cliente_envio_tasks(conn: sqlite3.Connection, *, current: datetime) -> list[dict[str, object]]:
    items = []
    for envio in list_cliente_envios(conn):
        state_value = clean_text(envio.get("estado"))
        if state_value not in CLIENTE_ENVIO_PENDIENTES_AGENDA:
            continue
        event_reference = (
            envio.get("correo_generado_at")
            or envio.get("updated_at")
            or envio.get("created_at")
            or ""
        )
        event_dt = agenda_parse_datetime(event_reference)
        linked = [{
            "id": envio.get("licitacion_id") or 0,
            "expediente": envio.get("licitacion_expediente") or "",
            "organismo": envio.get("licitacion_organismo") or "",
            "objeto": envio.get("licitacion_objeto") or "",
            "estado": envio.get("estado_label") or "",
            "enlace_perfil": envio.get("licitacion_enlace_perfil") or "",
        }]
        items.append({
            "id": f"cliente_envio:{envio['id']}",
            "type": "cliente_envio",
            "source_type": "cliente_envio",
            "source_id": int(envio["id"]),
            "title": f"{envio.get('cliente_nombre') or 'Cliente'} · {envio.get('tipo_envio_label') or 'Envío'}",
            "subtitle": envio.get("asunto") or envio.get("licitacion_objeto") or envio.get("actuacion_titulo") or "Envío a cliente",
            "description": envio.get("licitacion_expediente") or envio.get("destinatario_email") or "",
            "status": envio.get("estado_label") or "",
            "state": envio.get("estado_label") or "",
            "state_value": state_value,
            "raw_state": envio.get("estado") or "",
            "cliente_nombre": envio.get("cliente_nombre") or "",
            "destinatario_email": envio.get("destinatario_email") or "",
            "expediente": envio.get("licitacion_expediente") or "",
            "objeto": envio.get("licitacion_objeto") or "",
            "tipo": envio.get("tipo_envio_label") or "",
            "ruta_carpeta": envio.get("carpeta_dropbox") or "",
            "correo_generado_path": envio.get("correo_generado_path") or "",
            "correo_generado_formato": envio.get("correo_generado_formato") or "",
            "incidencia_detalle": envio.get("incidencia_detalle") or "",
            "linked_licitaciones": linked,
            "pending_panel": _cliente_envio_panel_key(state_value),
            "state_options": TASK_STATE_OPTIONS,
            **_event_parts(event_dt, current=current),
        })
    return items


def _pending_panels(items: list[dict[str, object]]) -> list[dict[str, object]]:
    regular_items = [item for item in items if item.get("source_type") != "cliente_envio"]
    panel_items = {
        "regular": regular_items,
        "ready": [item for item in items if item.get("pending_panel") == "ready"],
        "generated": [item for item in items if item.get("pending_panel") == "generated"],
        "incidents": [item for item in items if item.get("pending_panel") == "incidents"],
    }
    order = ["regular", "ready", "generated", "incidents"]
    panels: list[dict[str, object]] = []
    for key in order:
        current_items = sorted(panel_items[key], key=_task_sort_key)
        if not current_items:
            continue
        panels.append(
            {
                "key": key,
                "title": CLIENTE_ENVIO_PANEL_TITLES.get(key, "Pendientes"),
                "items": current_items,
            }
        )
    return panels


def build_pending_tasks_response(
    conn: sqlite3.Connection,
    *,
    query: str = "",
    current: datetime | None = None,
) -> dict[str, object]:
    current_dt = current or datetime.now().replace(microsecond=0)
    items = [
        *_licitacion_tasks(conn, current=current_dt),
        *_actuacion_tasks(conn, current=current_dt),
        *_internal_event_tasks(conn, current=current_dt),
        *_cliente_envio_tasks(conn, current=current_dt),
    ]
    filtered = [item for item in items if _matches_query(item, query)]
    ordered = sorted(filtered, key=_task_sort_key)
    return {
        "ok": True,
        "items": ordered,
        "groups": _groups(ordered),
        "panels": _pending_panels(ordered),
    }
