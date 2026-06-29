from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from types import ModuleType

from webapp.infonalia_webapp.tests.test_delete_dia_endpoint import (
    count_rows,
    foreign_key_check_rows,
    insert_dia,
    insert_licitacion,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
    temporary_app_database,
)


def teardown_function() -> None:
    sys.modules.pop("app", None)
    sys.modules.pop("webapp.infonalia_webapp.app", None)


def make_handler(
    app: ModuleType,
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    csrf_token: str | None = VALID_CSRF_TOKEN,
    username: str = "admin_test",
    role: str = "admin",
    email: str = "admin@example.test",
):
    body = json.dumps(payload or {}).encode("utf-8")
    handler = object.__new__(app.InfonaliaHandler)
    handler.path = path
    handler.rfile = io.BytesIO(body)
    handler.headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    if csrf_token is not None:
        handler.headers[app.CSRF_HEADER] = csrf_token
    handler.responses = []
    handler.errors = []
    handler.current_user = lambda: {
        "username": username,
        "role": role,
        "display_name": username,
        "email": email,
        "csrf_token": VALID_CSRF_TOKEN,
    }

    def send_json(response_payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, response_payload))

    def send_error(status: HTTPStatus, message: str = "") -> None:
        handler.errors.append((status, message))

    handler.send_json = send_json
    handler.send_error = send_error
    return handler


def dispatch(handler, method: str) -> None:
    getattr(handler, f"do_{method}")()


def create_actuacion(app: ModuleType, licitacion_ids: list[int] | None = None, **overrides: object) -> dict:
    payload = {
        "tipo": "requerimiento",
        "titulo": "Aportar documentación",
        "descripcion": "Subir anexos requeridos",
        "deadline_at": (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat(),
        "recordatorio_email": True,
        "origen": "manual",
        "licitacion_ids": licitacion_ids or [],
    }
    payload.update(overrides)
    handler = make_handler(app, "POST", "/api/actuaciones", payload)
    dispatch(handler, "POST")
    assert handler.responses[-1][0] == HTTPStatus.CREATED
    return handler.responses[-1][1]["item"]


def list_actuaciones(app: ModuleType, query: str = "") -> list[dict]:
    handler = make_handler(app, "GET", f"/api/actuaciones{query}", {})
    dispatch(handler, "GET")
    assert handler.responses[-1][0] == HTTPStatus.OK
    return handler.responses[-1][1]["items"]


def list_licitaciones(app: ModuleType, query: str = "") -> dict:
    handler = make_handler(app, "GET", f"/api/licitaciones{query}", {})
    dispatch(handler, "GET")
    assert handler.responses[-1][0] == HTTPStatus.OK
    return handler.responses[-1][1]


def detail_actuacion(app: ModuleType, actuacion_id: int) -> dict:
    handler = make_handler(app, "GET", f"/api/actuaciones/{actuacion_id}", {})
    dispatch(handler, "GET")
    assert handler.responses[-1][0] == HTTPStatus.OK
    return handler.responses[-1][1]["item"]


def mark_dia_as_reviewed(app: ModuleType, dia_id: int) -> None:
    timestamp = datetime(2026, 6, 14, 12, 0, 0).isoformat()
    with app.db_session() as conn:
        conn.execute(
            """
            UPDATE infonalia_dias
            SET estado = 'Completado',
                reviewed_at = ?,
                nuria_dirty_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, dia_id),
        )


def dia_review_state(app: ModuleType, dia_id: int) -> dict:
    with app.db_session() as conn:
        row = conn.execute(
            "SELECT estado, reviewed_at, nuria_dirty_at FROM infonalia_dias WHERE id = ?",
            (dia_id,),
        ).fetchone()
        return dict(row)


def test_create_actuacion_without_licitacion_and_filter() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        item = create_actuacion(app, None)
        rows = list_actuaciones(app, "?sin_licitacion=1")

        assert item["licitaciones"] == []
        assert item["licitaciones_count"] == 0
        assert rows[0]["titulo"] == "Aportar documentación"
        assert count_rows(app, "actuaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 0
        assert foreign_key_check_rows(app) == []


def test_create_actuacion_with_one_and_multiple_licitaciones() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_a = insert_licitacion(app, dia_id, "ACT-001")
        licitacion_b = insert_licitacion(app, dia_id, "ACT-002")

        one = create_actuacion(app, [licitacion_a], titulo="Una")
        multiple = create_actuacion(app, [licitacion_a, licitacion_b, licitacion_a], titulo="Varias")
        rows = list_actuaciones(app, f"?licitacion_id={licitacion_b}")

        assert [item["id"] for item in one["licitaciones"]] == [licitacion_a]
        assert [item["id"] for item in multiple["licitaciones"]] == [licitacion_a, licitacion_b]
        assert [item["titulo"] for item in rows] == ["Varias"]
        assert count_rows(app, "actuacion_licitaciones") == 3


def test_update_licitaciones_and_detail_history() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_a = insert_licitacion(app, dia_id, "ACT-003")
        licitacion_b = insert_licitacion(app, dia_id, "ACT-004")
        item = create_actuacion(app, [licitacion_a])

        patch = make_handler(
            app,
            "PATCH",
            f"/api/actuaciones/{item['id']}",
            {"licitacion_ids": [licitacion_b], "estado": "en_curso"},
        )
        dispatch(patch, "PATCH")
        assert patch.responses[-1][0] == HTTPStatus.OK

        comment = make_handler(
            app,
            "POST",
            f"/api/actuaciones/{item['id']}/historial",
            {"comentario": "Comentario de seguimiento"},
        )
        dispatch(comment, "POST")
        assert comment.responses[-1][0] == HTTPStatus.CREATED

        detail = detail_actuacion(app, item["id"])
        assert [linked["id"] for linked in detail["licitaciones"]] == [licitacion_b]
        event_types = [entry["event_type"] for entry in detail["historial"]]
        assert "creacion" in event_types
        assert "licitaciones" in event_types
        assert "estado" in event_types
        assert "comentario" in event_types


def test_duplicate_actuacion_copies_main_fields_and_links_without_old_history() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_a = insert_licitacion(app, dia_id, "ACT-DUP-001")
        item = create_actuacion(
            app,
            [licitacion_a],
            titulo="Actuación a duplicar",
            descripcion="Descripción duplicable",
            deadline_at="2026-06-20T10:30:00",
        )
        comment = make_handler(
            app,
            "POST",
            f"/api/actuaciones/{item['id']}/historial",
            {"comentario": "Comentario que no se copia"},
        )
        dispatch(comment, "POST")

        duplicate = make_handler(app, "POST", f"/api/actuaciones/{item['id']}/duplicar", {})
        dispatch(duplicate, "POST")

        assert duplicate.responses[-1][0] == HTTPStatus.CREATED
        copied = duplicate.responses[-1][1]["item"]
        assert copied["id"] != item["id"]
        assert copied["titulo"] == "Actuación a duplicar (copia)"
        assert copied["descripcion"] == "Descripción duplicable"
        assert copied["deadline_at"] == "2026-06-20T10:30:00"
        assert [linked["id"] for linked in copied["licitaciones"]] == [licitacion_a]
        assert [entry["event_type"] for entry in copied["historial"]] == ["duplicado"]
        assert "Comentario que no se copia" not in json.dumps(copied["historial"])


def test_list_actuaciones_filters_vencidas_hoy_semana(monkeypatch) -> None:
    app = load_app_module()
    fixed_now = datetime(2026, 6, 14, 12, 0, 0)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            if tz is not None:
                return fixed_now.replace(tzinfo=tz)
            return fixed_now

    with temporary_app_database(app):
        create_actuacion(app, None, titulo="Vencida", deadline_at=(fixed_now - timedelta(hours=2)).isoformat())
        create_actuacion(app, None, titulo="Hoy", deadline_at=(fixed_now + timedelta(minutes=30)).isoformat())
        create_actuacion(app, None, titulo="Semana", deadline_at=(fixed_now + timedelta(days=3)).isoformat())
        monkeypatch.setattr(app, "datetime", FixedDatetime)

        assert [item["titulo"] for item in list_actuaciones(app, "?vencidas=1")] == ["Vencida"]
        assert [item["titulo"] for item in list_actuaciones(app, "?hoy=1")] == ["Hoy"]
        assert [item["titulo"] for item in list_actuaciones(app, "?semana=1")] == ["Semana"]


def test_licitaciones_expose_actuacion_indicators_and_filters() -> None:
    app = load_app_module()
    now = datetime.now().replace(microsecond=0)
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        lic_open = insert_licitacion(app, dia_id, "LIC-ACT-ABIERTA")
        lic_overdue = insert_licitacion(app, dia_id, "LIC-ACT-VENCIDA")
        lic_without_date = insert_licitacion(app, dia_id, "LIC-ACT-SIN-FECHA")
        lic_without_open = insert_licitacion(app, dia_id, "LIC-SIN-ABIERTAS")
        create_actuacion(app, [lic_open], titulo="Act abierta", deadline_at=(now + timedelta(days=2)).isoformat())
        create_actuacion(app, [lic_overdue], titulo="Act vencida", deadline_at=(now - timedelta(days=1)).isoformat())
        create_actuacion(app, [lic_without_date], titulo="Act sin fecha", deadline_at="")
        create_actuacion(app, [lic_without_open], titulo="Act cerrada", estado="cerrada")

        all_items = list_licitaciones(app)["items"]
        abiertas = list_licitaciones(app, "?actuaciones=abiertas")["items"]
        vencidas = list_licitaciones(app, "?actuaciones=vencidas")["items"]
        sin_fecha = list_licitaciones(app, "?actuaciones=sin_fecha")["items"]
        sin_abiertas = list_licitaciones(app, "?actuaciones=sin_abiertas")["items"]

    by_exp = {item["expediente"]: item for item in all_items}
    assert by_exp["LIC-ACT-ABIERTA"]["actuaciones_abiertas"] == 1
    assert by_exp["LIC-ACT-ABIERTA"]["proxima_actuacion_at"]
    assert by_exp["LIC-ACT-VENCIDA"]["actuaciones_vencidas"] == 1
    assert by_exp["LIC-ACT-SIN-FECHA"]["actuaciones_sin_fecha"] == 1
    assert {item["expediente"] for item in abiertas} == {"LIC-ACT-ABIERTA", "LIC-ACT-VENCIDA", "LIC-ACT-SIN-FECHA"}
    assert {item["expediente"] for item in vencidas} == {"LIC-ACT-VENCIDA"}
    assert {item["expediente"] for item in sin_fecha} == {"LIC-ACT-SIN-FECHA"}
    assert "LIC-SIN-ABIERTAS" in {item["expediente"] for item in sin_abiertas}


def test_centro_licitaciones_vivas_and_all_order_and_filters() -> None:
    app = load_app_module()
    states = [
        ("CENTRO-IMPORTADA", "Importada", "2026-06-15"),
        ("CENTRO-DESCARTADA", "Descartada", "2026-06-16"),
        ("CENTRO-NURIA", "Enviada a Nuria", "2026-06-17"),
        ("CENTRO-DESCARGAR", "Descargar para ver", "2030-06-18"),
        ("CENTRO-PREPARAR", "Preparar ficha", "2030-06-19"),
        ("CENTRO-PREPARADA", "Preparada", "2030-06-21"),
        ("CENTRO-OFERTA", "Oferta enviada", "2030-06-20"),
    ]
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        for expediente, estado, fecha_limite in states:
            licitacion_id = insert_licitacion(app, dia_id, expediente)
            with app.db_session() as conn:
                conn.execute(
                    """
                    UPDATE licitaciones
                    SET estado = ?, fecha_limite = ?, hora_limite = ?, organismo = ?
                    WHERE id = ?
                    """,
                    (estado, fecha_limite, "12:00", "Org Centro", licitacion_id),
                )

        live = list_licitaciones(app, "?vivas=1&orden_fecha=asc")["items"]
        managed = list_licitaciones(app, "?gestionadas=1&orden_fecha=asc")["items"]
        managed_default = list_licitaciones(app, "?gestionadas=1")["items"]
        all_items = list_licitaciones(app, "?orden_fecha=desc")["items"]
        by_estado = list_licitaciones(app, "?estado=Preparar%20ficha")["items"]
        by_search = list_licitaciones(app, "?q=PREPARADA")["items"]

    assert [item["expediente"] for item in live] == [
        "CENTRO-DESCARGAR",
        "CENTRO-PREPARAR",
        "CENTRO-PREPARADA",
    ]
    assert [item["expediente"] for item in managed] == [
        "CENTRO-DESCARGAR",
        "CENTRO-PREPARAR",
        "CENTRO-OFERTA",
        "CENTRO-PREPARADA",
    ]
    assert [item["expediente"] for item in managed_default] == [
        "CENTRO-DESCARGAR",
        "CENTRO-PREPARAR",
        "CENTRO-OFERTA",
        "CENTRO-PREPARADA",
    ]
    assert [item["expediente"] for item in all_items][:2] == ["CENTRO-PREPARADA", "CENTRO-OFERTA"]
    assert [item["expediente"] for item in by_estado] == ["CENTRO-PREPARAR"]
    assert [item["expediente"] for item in by_search] == ["CENTRO-PREPARADA"]


def test_centro_licitaciones_date_hierarchy_filters_by_fecha_presentacion() -> None:
    app = load_app_module()
    rows = [
        ("FILTRO-JUNIO", "Descargar para ver", "2030-06-10"),
        ("FILTRO-JULIO", "Preparar ficha", "2030-07-11"),
        ("FILTRO-DESCARTADA", "Descartada", "2030-06-12"),
        ("FILTRO-2029", "Preparada", "2029-05-02"),
        ("FILTRO-SIN-FECHA", "Descargar para ver", ""),
        ("FILTRO-PREPARAR-TEXTO", "preparar", "2030-08-01"),
        ("FILTRO-FECHA-RARA", "Preparada", "sin fecha"),
    ]
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        for expediente, estado, fecha_limite in rows:
            licitacion_id = insert_licitacion(app, dia_id, expediente)
            with app.db_session() as conn:
                conn.execute(
                    """
                    UPDATE licitaciones
                    SET estado = ?, fecha_limite = ?, hora_limite = ?
                    WHERE id = ?
                    """,
                    (estado, fecha_limite, "12:00", licitacion_id),
                )

        junio_live = list_licitaciones(app, "?vivas=1&ejercicio=2030&mes=6&orden_fecha=asc")
        gestionadas = list_licitaciones(app, "?gestionadas=1&ejercicio=2030&orden_fecha=asc")
        gestionadas_default = list_licitaciones(app, "?gestionadas=1")
        todas = list_licitaciones(app, "?orden_fecha=asc")
        todas_2030 = list_licitaciones(app, "?ejercicio=2030&orden_fecha=asc")

    assert [item["expediente"] for item in junio_live["items"]] == ["FILTRO-JUNIO"]
    assert "2030" in junio_live["date_filters"]["years"]
    assert "2029" in junio_live["date_filters"]["years"]
    assert junio_live["date_filters"]["year_all_count"] == 3
    assert junio_live["date_filters"]["month_all_count"] == 2
    assert junio_live["date_filters"]["month_counts"]["6"] == 1
    assert junio_live["date_filters"]["month_counts"]["7"] == 1
    assert "FILTRO-SIN-FECHA" in {item["expediente"] for item in todas["items"]}
    assert "FILTRO-PREPARAR-TEXTO" in {item["expediente"] for item in gestionadas["items"]}
    assert set(item["expediente"] for item in gestionadas_default["items"][-2:]) == {
        "FILTRO-FECHA-RARA",
        "FILTRO-SIN-FECHA",
    }
    assert gestionadas["date_filters"]["month_counts"]["8"] == 1
    assert todas["date_filters"]["year_all_count"] == 7
    assert todas["date_filters"]["month_all_count"] == 7
    assert "FILTRO-SIN-FECHA" not in {item["expediente"] for item in todas_2030["items"]}
    assert todas_2030["date_filters"]["month_all_count"] == 4


def test_licitacion_review_state_transitions_for_admin_and_nuria() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        to_discard = insert_licitacion(app, dia_id, "REV-DESCARTAR")
        to_nuria_download = insert_licitacion(app, dia_id, "REV-NURIA-DESCARGAR")
        to_nuria_prepare = insert_licitacion(app, dia_id, "REV-NURIA-PREPARAR")

        admin_discard = make_handler(app, "PATCH", f"/api/licitaciones/{to_discard}", {"estado": "Descartada"})
        dispatch(admin_discard, "PATCH")
        admin_nuria_download = make_handler(
            app,
            "PATCH",
            f"/api/licitaciones/{to_nuria_download}",
            {"estado": "Enviada a Nuria"},
        )
        dispatch(admin_nuria_download, "PATCH")
        admin_nuria_prepare = make_handler(
            app,
            "PATCH",
            f"/api/licitaciones/{to_nuria_prepare}",
            {"estado": "Enviada a Nuria"},
        )
        dispatch(admin_nuria_prepare, "PATCH")

        nuria_download = make_handler(
            app,
            "PATCH",
            f"/api/licitaciones/{to_nuria_download}",
            {"estado": "Descargar para ver"},
            username="reviewer_test",
            role="nuria",
        )
        dispatch(nuria_download, "PATCH")
        nuria_prepare = make_handler(
            app,
            "PATCH",
            f"/api/licitaciones/{to_nuria_prepare}",
            {"estado": "Preparar ficha"},
            username="reviewer_test",
            role="nuria",
        )
        dispatch(nuria_prepare, "PATCH")

    assert admin_discard.responses[-1][0] == HTTPStatus.OK
    assert admin_discard.responses[-1][1]["estado"] == "Descartada"
    assert admin_nuria_download.responses[-1][0] == HTTPStatus.OK
    assert admin_nuria_download.responses[-1][1]["estado"] == "Enviada a Nuria"
    assert admin_nuria_prepare.responses[-1][0] == HTTPStatus.OK
    assert admin_nuria_prepare.responses[-1][1]["estado"] == "Enviada a Nuria"
    assert nuria_download.responses[-1][0] == HTTPStatus.OK
    assert nuria_download.responses[-1][1]["estado"] == "Descargar para ver"
    assert nuria_prepare.responses[-1][0] == HTTPStatus.OK
    assert nuria_prepare.responses[-1][1]["estado"] == "Preparar ficha"


def test_nuria_day_review_hides_discarded_by_default_and_can_filter_them() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        states = {
            "NURIA-DESC-1": "Descartada",
            "NURIA-DESC-2": "Descartada",
            "NURIA-ENVIADA": "Enviada a Nuria",
            "NURIA-DESCARGAR": "Descargar para ver",
            "NURIA-PREPARAR": "Preparar ficha",
            "NURIA-PREPARADA": "Preparada",
            "NURIA-OFERTA": "Oferta enviada",
        }
        inserted = []
        for expediente, estado in states.items():
            inserted.append((insert_licitacion(app, dia_id, expediente), estado))
        with app.db_session() as conn:
            for licitacion_id, estado in inserted:
                conn.execute("UPDATE licitaciones SET estado = ? WHERE id = ?", (estado, licitacion_id))

        default_handler = make_handler(
            app,
            "GET",
            f"/api/licitaciones?dia_id={dia_id}",
            username="reviewer_test",
            role="nuria",
        )
        dispatch(default_handler, "GET")
        all_handler = make_handler(
            app,
            "GET",
            f"/api/licitaciones?dia_id={dia_id}&nuria_filter=all",
            username="reviewer_test",
            role="nuria",
        )
        dispatch(all_handler, "GET")
        discarded_handler = make_handler(
            app,
            "GET",
            f"/api/licitaciones?dia_id={dia_id}&nuria_filter=discarded",
            username="reviewer_test",
            role="nuria",
        )
        dispatch(discarded_handler, "GET")

    assert default_handler.responses[-1][0] == HTTPStatus.OK
    default_items = {item["expediente"] for item in default_handler.responses[-1][1]["items"]}
    assert default_items == {
        "NURIA-ENVIADA",
        "NURIA-DESCARGAR",
        "NURIA-PREPARAR",
        "NURIA-PREPARADA",
        "NURIA-OFERTA",
    }
    assert "Descartada" not in default_handler.responses[-1][1]["estados"]

    assert all_handler.responses[-1][0] == HTTPStatus.OK
    all_items = {item["expediente"] for item in all_handler.responses[-1][1]["items"]}
    assert all_items == set(states)
    assert "Descartada" in all_handler.responses[-1][1]["estados"]

    assert discarded_handler.responses[-1][0] == HTTPStatus.OK
    discarded_items = {item["expediente"] for item in discarded_handler.responses[-1][1]["items"]}
    assert discarded_items == {"NURIA-DESC-1", "NURIA-DESC-2"}


def test_admin_day_review_still_lists_imported_and_review_states() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        imported = insert_licitacion(app, dia_id, "ADMIN-IMPORTADA")
        discarded = insert_licitacion(app, dia_id, "ADMIN-DESCARTADA")
        sent = insert_licitacion(app, dia_id, "ADMIN-ENVIADA")
        with app.db_session() as conn:
            conn.execute("UPDATE licitaciones SET estado = 'Importada' WHERE id = ?", (imported,))
            conn.execute("UPDATE licitaciones SET estado = 'Descartada' WHERE id = ?", (discarded,))
            conn.execute("UPDATE licitaciones SET estado = 'Enviada a Nuria' WHERE id = ?", (sent,))

        handler = make_handler(app, "GET", f"/api/licitaciones?dia_id={dia_id}")
        dispatch(handler, "GET")

    assert handler.responses[-1][0] == HTTPStatus.OK
    expedientes = {item["expediente"] for item in handler.responses[-1][1]["items"]}
    assert expedientes == {"ADMIN-IMPORTADA", "ADMIN-DESCARTADA", "ADMIN-ENVIADA"}


def test_nuria_center_list_is_not_changed_by_day_review_filter() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        states = {
            "CENTRO-NURIA-DESC": "Descartada",
            "CENTRO-NURIA-ENVIADA": "Enviada a Nuria",
            "CENTRO-NURIA-DESCARGAR": "Descargar para ver",
            "CENTRO-NURIA-PREPARAR": "Preparar ficha",
            "CENTRO-NURIA-PREPARADA": "Preparada",
        }
        inserted = []
        for expediente, estado in states.items():
            inserted.append((insert_licitacion(app, dia_id, expediente), estado))
        with app.db_session() as conn:
            for licitacion_id, estado in inserted:
                conn.execute("UPDATE licitaciones SET estado = ? WHERE id = ?", (estado, licitacion_id))

        handler = make_handler(app, "GET", "/api/licitaciones", username="reviewer_test", role="nuria")
        dispatch(handler, "GET")

    assert handler.responses[-1][0] == HTTPStatus.OK
    expedientes = {item["expediente"] for item in handler.responses[-1][1]["items"]}
    assert expedientes == set(states)


def test_nuria_and_admin_center_receive_same_general_licitacion_items() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        states = {
            "CENTRO-COMUN-IMPORTADA": "Importada",
            "CENTRO-COMUN-DESCARTADA": "Descartada",
            "CENTRO-COMUN-ENVIADA": "Enviada a Nuria",
            "CENTRO-COMUN-DESCARGAR": "Descargar para ver",
            "CENTRO-COMUN-PREPARAR": "Preparar ficha",
            "CENTRO-COMUN-PREPARADA": "Preparada",
            "CENTRO-COMUN-OFERTA": "Oferta enviada",
        }
        inserted = []
        for expediente, estado in states.items():
            inserted.append((insert_licitacion(app, dia_id, expediente), estado))
        with app.db_session() as conn:
            for licitacion_id, estado in inserted:
                conn.execute("UPDATE licitaciones SET estado = ? WHERE id = ?", (estado, licitacion_id))

        admin = make_handler(app, "GET", "/api/licitaciones", username="admin_test", role="admin")
        nuria = make_handler(app, "GET", "/api/licitaciones", username="reviewer_test", role="nuria")
        dispatch(admin, "GET")
        dispatch(nuria, "GET")

    assert admin.responses[-1][0] == HTTPStatus.OK
    assert nuria.responses[-1][0] == HTTPStatus.OK
    admin_exp = {item["expediente"] for item in admin.responses[-1][1]["items"]}
    nuria_exp = {item["expediente"] for item in nuria.responses[-1][1]["items"]}
    assert admin_exp == nuria_exp == set(states)


def test_licitacion_detail_lists_linked_actuaciones_and_comment_summary() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "LIC-DET-ACT")
        item = create_actuacion(app, [licitacion_id], titulo="Act detalle")
        comment = make_handler(
            app,
            "POST",
            f"/api/actuaciones/{item['id']}/historial",
            {"comentario": "Comentario visible"},
        )
        dispatch(comment, "POST")

        handler = make_handler(app, "GET", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "GET")

    assert handler.responses[-1][0] == HTTPStatus.OK
    detail = handler.responses[-1][1]["item"]
    assert detail["actuaciones_abiertas"] == 1
    assert detail["actuaciones"][0]["titulo"] == "Act detalle"
    assert detail["actuaciones"][0]["ultimo_comentario"] == "Comentario visible"
    assert detail["actuaciones"][0]["historial_count"] >= 2


def test_licitacion_detail_updates_review_notes_internal_state_and_followup() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "LIC-CENTRO")

        patch = make_handler(
            app,
            "PATCH",
            f"/api/licitaciones/{licitacion_id}",
            {
                "revisada": True,
                "estado_interno": "En estudio",
                "notas_internas": "Mirar solvencia",
            },
        )
        dispatch(patch, "PATCH")
        assert patch.responses[-1][0] == HTTPStatus.OK

        detail_handler = make_handler(app, "GET", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(detail_handler, "GET")
        revisadas = list_licitaciones(app, "?revision=revisada")["items"]
        seguimiento = list_licitaciones(app, "?seguimiento=1")["items"]
        estado = list_licitaciones(app, "?estado_interno=En%20estudio")["items"]

    detail = detail_handler.responses[-1][1]["item"]
    assert detail["revisada"] is True
    assert detail["estado_interno"] == "En estudio"
    assert detail["notas_internas"] == "Mirar solvencia"
    assert detail["seguimiento"]["activo"] is False
    assert detail["seguimiento"]["fuente"] == "marcador Dropbox"
    assert {entry["event_type"] for entry in detail["historial"]} >= {
        "reviewed_at",
        "estado_interno",
        "notas_internas",
    }
    assert [item["id"] for item in revisadas] == [licitacion_id]
    assert seguimiento == []
    assert [item["id"] for item in estado] == [licitacion_id]


def test_updating_licitacion_state_keeps_reviewed_day_closed() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "LIC-DIA-CERRADO")
        mark_dia_as_reviewed(app, dia_id)

        patch = make_handler(
            app,
            "PATCH",
            f"/api/licitaciones/{licitacion_id}",
            {"estado": app.ESTADO_PREPARAR_FICHA},
        )
        dispatch(patch, "PATCH")

        state = dia_review_state(app, dia_id)

    assert patch.responses[-1][0] == HTTPStatus.OK
    assert state["estado"] == "Completado"
    assert state["reviewed_at"]
    assert not state["nuria_dirty_at"]
    assert app.is_nuria_update_pending(state) is False


def test_editing_licitacion_fields_keeps_reviewed_day_closed() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "LIC-DIA-EDIT")
        mark_dia_as_reviewed(app, dia_id)

        patch = make_handler(
            app,
            "PATCH",
            f"/api/licitaciones/{licitacion_id}",
            {"objeto": "Servicio ficticio corregido"},
        )
        dispatch(patch, "PATCH")

        state = dia_review_state(app, dia_id)

    assert patch.responses[-1][0] == HTTPStatus.OK
    assert state["estado"] == "Completado"
    assert state["reviewed_at"]
    assert not state["nuria_dirty_at"]


def test_creating_actuacion_for_licitacion_keeps_reviewed_day_closed() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "LIC-DIA-ACT")
        mark_dia_as_reviewed(app, dia_id)

        create_actuacion(app, [licitacion_id])

        state = dia_review_state(app, dia_id)

    assert state["estado"] == "Completado"
    assert state["reviewed_at"]
    assert not state["nuria_dirty_at"]


def test_unmark_dia_revisado_explicitly_reopens_day() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        insert_licitacion(app, dia_id, "LIC-DIA-REOPEN")
        mark_dia_as_reviewed(app, dia_id)

        handler = make_handler(app, "POST", f"/api/dias/{dia_id}/desmarcar-revisado", {})
        dispatch(handler, "POST")

        state = dia_review_state(app, dia_id)

    assert handler.responses[-1][0] == HTTPStatus.OK
    assert not state["reviewed_at"]
    assert state["estado"] != "Completado"


def test_licitacion_detail_lists_and_classifies_downloaded_documents(tmp_path) -> None:
    app = load_app_module()
    folder = tmp_path / "expediente"
    folder.mkdir()
    (folder / "PCAP contrato.pdf").write_bytes(b"pcap")
    (folder / "PPT tecnico.pdf").write_bytes(b"ppt")
    (folder / ".infonalia_manifest.json").write_text("{}", encoding="utf-8")
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "LIC-DOCS")
        with app.db_session() as conn:
            conn.execute(
                "UPDATE licitaciones SET ruta_carpeta = ? WHERE id = ?",
                (str(folder), licitacion_id),
            )

        handler = make_handler(app, "GET", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "GET")

    docs = handler.responses[-1][1]["item"]["documentos"]
    assert [doc["name"] for doc in docs] == ["PCAP contrato.pdf", "PPT tecnico.pdf"]
    assert {doc["category"] for doc in docs} == {"PCAP", "PPT"}
    assert handler.responses[-1][1]["item"]["documentacion"]["count"] == 2


def test_close_and_cancel_actuacion() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        item = create_actuacion(app, None)

        close = make_handler(app, "POST", f"/api/actuaciones/{item['id']}/cerrar", {})
        dispatch(close, "POST")
        assert close.responses[-1][1]["item"]["estado"] == "cerrada"
        assert close.responses[-1][1]["item"]["closed_at"]

        second = create_actuacion(app, None, titulo="Cancelar")
        cancel = make_handler(app, "POST", f"/api/actuaciones/{second['id']}/cancelar", {})
        dispatch(cancel, "POST")
        assert cancel.responses[-1][1]["item"]["estado"] == "cancelada"


def test_licitaciones_search_for_selector() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        insert_licitacion(app, dia_id, "SEL-001")
        insert_licitacion(app, dia_id, "OTRA-002")

        handler = make_handler(app, "GET", "/api/licitaciones/search?q=SEL", {})
        dispatch(handler, "GET")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert [item["expediente"] for item in handler.responses[-1][1]["items"]] == ["SEL-001"]


def test_actuacion_mutations_reject_missing_csrf() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        handler = make_handler(
            app,
            "POST",
            "/api/actuaciones",
            {"titulo": "Sin CSRF"},
            csrf_token=None,
        )

        dispatch(handler, "POST")

        assert handler.responses[-1][0] == HTTPStatus.FORBIDDEN
        assert count_rows(app, "actuaciones") == 0


def test_delete_licitacion_with_open_actuacion_is_blocked() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DEL")
        create_actuacion(app, [licitacion_id])

        handler = make_handler(app, "DELETE", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert handler.responses[-1][1]["error"] == "No se puede borrar la licitación porque tiene actuaciones abiertas."
        assert count_rows(app, "licitaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 1


def test_delete_dia_with_open_actuacion_is_blocked() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DIA")
        create_actuacion(app, [licitacion_id])

        handler = make_handler(app, "DELETE", f"/api/dias/{dia_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.CONFLICT
        assert handler.responses[-1][1]["error"] == "No se puede borrar el día porque contiene licitaciones con actuaciones abiertas."
        assert count_rows(app, "infonalia_dias") == 1
        assert count_rows(app, "licitaciones") == 1


def test_delete_licitacion_with_closed_actuacion_only_unlinks_relation() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-CLOSED")
        item = create_actuacion(app, [licitacion_id], estado="cerrada")

        handler = make_handler(app, "DELETE", f"/api/licitaciones/{licitacion_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "actuaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 0
        assert detail_actuacion(app, item["id"])["estado"] == "cerrada"
        assert foreign_key_check_rows(app) == []


def test_delete_dia_with_closed_actuacion_only_unlinks_relations() -> None:
    app = load_app_module()
    with temporary_app_database(app):
        dia_id = insert_dia(app)
        licitacion_id = insert_licitacion(app, dia_id, "ACT-DIA-CLOSED")
        create_actuacion(app, [licitacion_id], estado="cancelada")

        handler = make_handler(app, "DELETE", f"/api/dias/{dia_id}", {})
        dispatch(handler, "DELETE")

        assert handler.responses[-1][0] == HTTPStatus.OK
        assert count_rows(app, "infonalia_dias") == 0
        assert count_rows(app, "licitaciones") == 0
        assert count_rows(app, "actuaciones") == 1
        assert count_rows(app, "actuacion_licitaciones") == 0
        assert foreign_key_check_rows(app) == []
