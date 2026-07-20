from __future__ import annotations

import hashlib
import io
import json
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType

import pytest
from openpyxl import Workbook
from PIL import Image

from webapp.infonalia_webapp.dropbox_paths import LicitacionFolderResolution
from webapp.infonalia_webapp.justificaciones_baja.application.dto import initial_draft
from webapp.infonalia_webapp.justificaciones_baja.persistence import JustificationRepository
from webapp.infonalia_webapp.justificaciones_baja.persistence.repository import canonical_json
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    VALID_CSRF_TOKEN,
    load_app_module,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TEST_TEMP_ROOT = REPOSITORY_ROOT / "tmp" / "justificaciones_baja_api_tests"


@dataclass(frozen=True)
class ApiEnvironment:
    app: ModuleType
    root: Path
    dropbox_base: Path
    licitation_folder: Path
    licitacion_id: int
    cliente_id: int


@contextmanager
def isolated_api_environment(
    app: ModuleType,
    monkeypatch: pytest.MonkeyPatch | None = None,
):
    TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    patcher = monkeypatch or pytest.MonkeyPatch()
    owns_patcher = monkeypatch is None
    old_values = {
        "DATA_ROOT": app.DATA_ROOT,
        "DOWNLOAD_ROOT": app.DOWNLOAD_ROOT,
        "DB_PATH": app.DB_PATH,
        "PROJECT_ROOT": app.PROJECT_ROOT,
    }
    with tempfile.TemporaryDirectory(prefix="api_", dir=TEST_TEMP_ROOT) as directory:
        root = Path(directory)
        app.DATA_ROOT = root / "data"
        app.DOWNLOAD_ROOT = app.DATA_ROOT / "descargas"
        app.DB_PATH = app.DATA_ROOT / "infonalia.db"
        app.PROJECT_ROOT = root
        app.init_db()
        dropbox_base = root / "dropbox"
        licitation_folder = dropbox_base / "Licitaciones" / "EXP-API-2026"
        licitation_folder.mkdir(parents=True)
        timestamp = "2026-07-14T12:00:00"
        with app.db_session() as conn:
            licitacion_id = int(
                conn.execute(
                    """
                    INSERT INTO licitaciones (
                        expediente, objeto, organismo, ruta_carpeta, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "EXP-API-2026",
                        "Suministro de alimentos",
                        "Ayuntamiento de Prueba",
                        "Licitaciones/EXP-API-2026",
                        timestamp,
                        timestamp,
                    ),
                ).lastrowid
            )
            cliente_id = int(
                conn.execute(
                    """
                    INSERT INTO clientes (
                        razon_social, nif_cif, domicilio_fiscal, codigo_postal,
                        municipio, provincia, telefono_principal, email_principal,
                        representante_nombre, representante_nif, representante_cargo,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Cliente API SL",
                        "B12345678",
                        "Calle Prueba 1",
                        "41001",
                        "Sevilla",
                        "Sevilla",
                        "955000000",
                        "cliente@example.test",
                        "Ana Representante",
                        "12345678Z",
                        "Administradora",
                        timestamp,
                        timestamp,
                    ),
                ).lastrowid
            )

        patcher.setattr(app, "validate_dropbox_base_path", lambda: dropbox_base)
        patcher.setattr(app, "resolve_licitacion_folder", lambda row, dropbox_base=None, _base=dropbox_base: LicitacionFolderResolution(
            ok=True,
            exists=True,
            inside_dropbox_base=True,
            path=str(licitation_folder),
            reason="ok",
            message="",
            base_path=str(dropbox_base or _base),
        ))
        try:
            yield ApiEnvironment(
                app=app,
                root=root,
                dropbox_base=dropbox_base,
                licitation_folder=licitation_folder,
                licitacion_id=licitacion_id,
                cliente_id=cliente_id,
            )
        finally:
            for name, value in old_values.items():
                setattr(app, name, value)
            if owns_patcher:
                patcher.undo()


@pytest.fixture
def api_environment(monkeypatch: pytest.MonkeyPatch) -> ApiEnvironment:
    app = load_app_module()
    with isolated_api_environment(app, monkeypatch) as environment:
        yield environment


def make_handler(
    app: ModuleType,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    *,
    raw_body: bytes | None = None,
    content_type: str = "application/json",
    csrf_token: str | None = VALID_CSRF_TOKEN,
    username: str = "admin_test",
    role: str = "admin",
):
    body = raw_body if raw_body is not None else json.dumps(payload or {}).encode("utf-8")
    handler = object.__new__(app.InfonaliaHandler)
    handler.path = path
    handler.rfile = io.BytesIO(body)
    handler.headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
    }
    if csrf_token is not None:
        handler.headers[app.CSRF_HEADER] = csrf_token
    handler.responses = []
    handler.errors = []
    handler.downloads = []
    handler.redirects = []
    handler.current_user = lambda: {
        "username": username,
        "role": role,
        "display_name": username,
        "email": f"{username}@example.test",
        "csrf_token": VALID_CSRF_TOKEN,
    }

    def send_json(response_payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        handler.responses.append((status, response_payload))

    def send_error(status: HTTPStatus, message: str = "") -> None:
        handler.errors.append((status, message))

    def send_private_document(content: bytes, filename: str, suffix: str) -> None:
        handler.downloads.append((content, filename, suffix))

    def redirect(location: str, clear_cookie: bool = False) -> None:
        handler.redirects.append((location, clear_cookie))

    handler.send_json = send_json
    handler.send_error = send_error
    handler.send_private_document = send_private_document
    handler.redirect = redirect
    return handler


def dispatch(handler, method: str) -> None:
    getattr(handler, f"do_{method}")()


def json_request(
    environment: ApiEnvironment,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    **handler_options: object,
) -> tuple[HTTPStatus, dict[str, object], object]:
    handler = make_handler(
        environment.app,
        method,
        path,
        payload,
        **handler_options,
    )
    dispatch(handler, method)
    assert handler.responses, f"La ruta {method} {path} no devolvió JSON"
    status, response = handler.responses[-1]
    assert isinstance(response, dict)
    return status, response, handler


def create_justification(
    environment: ApiEnvironment,
    *,
    offer: str = "20.00",
) -> dict[str, object]:
    status, response, _ = json_request(
        environment,
        "POST",
        "/api/justificaciones-baja",
        {
            "licitacion_id": environment.licitacion_id,
            "cliente_id": environment.cliente_id,
            "lote_numero": "1",
            "lote_nombre": "Productos de alimentación",
            "importe_ofertado": offer,
        },
    )
    assert status == HTTPStatus.CREATED
    return response["item"]


def complete_initial_draft(
    environment: ApiEnvironment,
    *,
    client_id: int | None = None,
) -> dict[str, object]:
    return initial_draft(
        licitacion={
            "id": environment.licitacion_id,
            "expediente": "EXP-API-2026",
            "objeto": "Suministro de alimentos",
            "organismo": "Ayuntamiento de Prueba",
        },
        cliente={
            "id": environment.cliente_id if client_id is None else client_id,
            "razon_social": "Cliente API SL",
            "nif_cif": "B12345678",
            "domicilio_fiscal": "Calle Prueba 1",
            "codigo_postal": "41001",
            "municipio": "Sevilla",
            "provincia": "Sevilla",
            "telefono_principal": "955000000",
            "email_principal": "cliente@example.test",
            "representante_nombre": "Ana Representante",
            "representante_nif": "12345678Z",
            "representante_cargo": "Administradora",
        },
        lote_numero="7",
        lote_nombre="Alimentos preparados",
        declared_offer="1234.56",
    )


def workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Oferta"
    sheet.append(["Producto", "Características", "Cantidad", "Precio", "Importe"])
    sheet.append(["PAN", "80 G", 10, 1, 10])
    sheet.append(["LECHE", "1 L", 5, 2, 10])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def multipart_xlsx_body(content: bytes) -> tuple[bytes, str]:
    boundary = "----justificaciones-api-test"
    fields = {
        "sheet_name": "Oferta",
        "start_row": "2",
        "preview_rows": "10",
        "mapping": json.dumps(
            {
                "name": "A",
                "characteristics": "B",
                "quantity": "C",
                "offered_unit_price": "D",
                "offered_amount": "E",
            }
        ),
    }
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            b'Content-Disposition: form-data; name="file"; filename="oferta.xlsx"\r\n',
            b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n",
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def pasted_products(environment: ApiEnvironment) -> list[dict[str, object]]:
    status, response, _ = json_request(
        environment,
        "POST",
        "/api/justificaciones-baja/pegar/preview",
        {
            "text": "Producto\tCantidad\tPrecio\nPAN\t10\t1\nLECHE\t5\t2",
            "start_row": 2,
            "mapping": {"name": 0, "quantity": 1, "offered_unit_price": 2},
        },
    )
    assert status == HTTPStatus.OK
    return response["preview"]["products"]


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 18), (50, 100, 150)).save(output, format="PNG")
    return output.getvalue()


def test_create_list_get_save_permissions_csrf_and_conflict(
    api_environment: ApiEnvironment,
) -> None:
    app = api_environment.app
    missing_csrf = make_handler(
        app,
        "POST",
        "/api/justificaciones-baja",
        {
            "licitacion_id": api_environment.licitacion_id,
            "cliente_id": api_environment.cliente_id,
        },
        csrf_token=None,
    )
    dispatch(missing_csrf, "POST")
    assert missing_csrf.responses[-1][0] == HTTPStatus.FORBIDDEN

    created = create_justification(api_environment)
    justification_id = int(created["id"])
    assert created["revision"] == 1
    assert created["draft"]["identification"]["expediente"] == "EXP-API-2026"

    status, listing, _ = json_request(
        api_environment,
        "GET",
        f"/api/justificaciones-baja?licitacion_id={api_environment.licitacion_id}",
        role="nuria",
        username="nuria_test",
    )
    assert status == HTTPStatus.OK
    assert [item["id"] for item in listing["items"]] == [justification_id]
    assert listing["permissions"] == {
        "view": True,
        "download": True,
        "create": False,
        "edit": False,
        "generate_costs": False,
        "freeze": False,
        "generate_documents": False,
        "change_state": False,
    }
    status, detail, _ = json_request(
        api_environment,
        "GET",
        f"/api/justificaciones-baja/{justification_id}",
        role="nuria",
        username="nuria_test",
    )
    assert status == HTTPStatus.OK
    assert detail["item"]["id"] == justification_id

    status, forbidden, _ = json_request(
        api_environment,
        "POST",
        "/api/justificaciones-baja",
        {
            "licitacion_id": api_environment.licitacion_id,
            "cliente_id": api_environment.cliente_id,
        },
        role="nuria",
        username="nuria_test",
    )
    assert status == HTTPStatus.FORBIDDEN
    assert "permiso" in forbidden["error"].lower()

    changed_draft = created["draft"]
    changed_draft["narrative"]["exposition"] = "Texto revisado por la asesoría."
    status, forbidden_edit, _ = json_request(
        api_environment,
        "PATCH",
        f"/api/justificaciones-baja/{justification_id}",
        {"revision": 1, "draft": changed_draft},
        role="nuria",
        username="nuria_test",
    )
    assert status == HTTPStatus.FORBIDDEN
    assert "permiso" in forbidden_edit["error"].lower()

    status, saved, _ = json_request(
        api_environment,
        "PATCH",
        f"/api/justificaciones-baja/{justification_id}",
        {"revision": 1, "draft": changed_draft},
    )
    assert status == HTTPStatus.OK
    assert saved["item"]["revision"] == 2
    assert saved["item"]["draft"]["narrative"]["exposition"].startswith("Texto revisado")

    status, conflict, _ = json_request(
        api_environment,
        "PATCH",
        f"/api/justificaciones-baja/{justification_id}",
        {"revision": 1, "draft": changed_draft},
    )
    assert status == HTTPStatus.CONFLICT
    assert conflict["code"] == "conflicto_revision"


def test_create_with_full_draft_is_atomic_and_persists_the_supplied_values(
    api_environment: ApiEnvironment,
) -> None:
    draft = complete_initial_draft(api_environment)
    draft["cost_range"] = {
        "minimum_percentage": 53,
        "maximum_percentage": 59,
    }
    draft["transport"]["shared_orders"] = 18
    draft["narrative"]["exposition"] = "Borrador completo recibido en la creación."

    status, response, _ = json_request(
        api_environment,
        "POST",
        "/api/justificaciones-baja",
        {
            "licitacion_id": api_environment.licitacion_id,
            "cliente_id": api_environment.cliente_id,
            "lote_numero": "7",
            "lote_nombre": "Alimentos preparados",
            "importe_ofertado": "1234.56",
            "draft": draft,
        },
    )
    assert status == HTTPStatus.CREATED
    item = response["item"]
    assert item["revision"] == 2
    assert item["cliente_id"] == api_environment.cliente_id
    assert item["draft"]["cost_range"] == {
        "minimum_percentage": 53,
        "maximum_percentage": 59,
    }
    assert item["draft"]["transport"]["shared_orders"] == 18
    assert item["draft"]["narrative"]["exposition"] == (
        "Borrador completo recibido en la creación."
    )
    assert [entry["event_type"] for entry in reversed(item["history"])] == [
        "created",
        "initial_draft_saved",
    ]

    with api_environment.app.db_session() as conn:
        before = int(conn.execute("SELECT COUNT(*) FROM justificaciones_baja").fetchone()[0])

    invalid_draft = complete_initial_draft(api_environment, client_id=999_999)
    status, invalid, _ = json_request(
        api_environment,
        "POST",
        "/api/justificaciones-baja",
        {
            "licitacion_id": api_environment.licitacion_id,
            "cliente_id": api_environment.cliente_id,
            "lote_numero": "8",
            "lote_nombre": "Cliente incoherente",
            "importe_ofertado": "1234.56",
            "draft": invalid_draft,
        },
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "cliente" in invalid["error"].lower()
    with api_environment.app.db_session() as conn:
        after = int(conn.execute("SELECT COUNT(*) FROM justificaciones_baja").fetchone()[0])
    assert after == before


def test_create_rejects_legacy_proposals_and_listing_consumes_q(
    api_environment: ApiEnvironment,
) -> None:
    with api_environment.app.db_session() as conn:
        before = int(conn.execute("SELECT COUNT(*) FROM justificaciones_baja").fetchone()[0])
    status, rejected, _ = json_request(
        api_environment,
        "POST",
        "/api/justificaciones-baja",
        {
            "licitacion_id": api_environment.licitacion_id,
            "cliente_id": api_environment.cliente_id,
            "lote_numero": "1",
            "importe_ofertado": "20.00",
            "proposals": {"minimum_percentage": 70, "maximum_percentage": 80},
        },
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "proposals" in rejected["error"]
    with api_environment.app.db_session() as conn:
        assert int(conn.execute("SELECT COUNT(*) FROM justificaciones_baja").fetchone()[0]) == before

    status, rejected_with_draft, _ = json_request(
        api_environment,
        "POST",
        "/api/justificaciones-baja",
        {
            "licitacion_id": api_environment.licitacion_id,
            "cliente_id": api_environment.cliente_id,
            "lote_numero": "1",
            "importe_ofertado": "20.00",
            "draft": complete_initial_draft(api_environment),
            "proposals": {"minimum_percentage": 70, "maximum_percentage": 80},
        },
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "proposals" in rejected_with_draft["error"]
    with api_environment.app.db_session() as conn:
        assert int(conn.execute("SELECT COUNT(*) FROM justificaciones_baja").fetchone()[0]) == before

    created = create_justification(api_environment)
    status, matched, _ = json_request(
        api_environment,
        "GET",
        "/api/justificaciones-baja?q=alimentaci%C3%B3n",
    )
    assert status == HTTPStatus.OK
    assert [item["id"] for item in matched["items"]] == [created["id"]]

    status, unmatched, _ = json_request(
        api_environment,
        "GET",
        "/api/justificaciones-baja?q=texto-que-no-existe",
    )
    assert status == HTTPStatus.OK
    assert unmatched["items"] == []


def test_paste_and_xlsx_preview_are_bounded_admin_operations(
    api_environment: ApiEnvironment,
) -> None:
    status, pasted, _ = json_request(
        api_environment,
        "POST",
        "/api/justificaciones-baja/pegar/preview",
        {
            "text": "Producto\tCantidad\tPrecio\nPAN\t10\t1\nLECHE\t5\t2",
            "start_row": 2,
            "mapping": {"name": 0, "quantity": 1, "offered_unit_price": 2},
            "preview_rows": 10,
        },
    )
    assert status == HTTPStatus.OK
    assert pasted["preview"]["format"] == "tabular"
    assert [item["name"] for item in pasted["preview"]["products"]] == ["PAN", "LECHE"]

    body, content_type = multipart_xlsx_body(workbook_bytes())
    handler = make_handler(
        api_environment.app,
        "POST",
        "/api/justificaciones-baja/importar-xlsx/preview",
        raw_body=body,
        content_type=content_type,
    )
    dispatch(handler, "POST")
    assert handler.responses[-1][0] == HTTPStatus.OK
    preview = handler.responses[-1][1]["preview"]
    assert preview["format"] == "xlsx"
    assert preview["sheet"] == "Oferta"
    assert [item["name"] for item in preview["products"]] == ["PAN", "LECHE"]
    assert preview["can_confirm"] is True

    status, forbidden, _ = json_request(
        api_environment,
        "POST",
        "/api/justificaciones-baja/pegar/preview",
        {"text": "PAN\t1\t1"},
        role="nuria",
        username="nuria_test",
    )
    assert status == HTTPStatus.FORBIDDEN
    assert "permiso" in forbidden["error"].lower()


def test_cost_actions_are_persisted_and_audited_through_api(
    api_environment: ApiEnvironment,
) -> None:
    created = create_justification(api_environment)
    justification_id = int(created["id"])
    products = pasted_products(api_environment)
    draft = created["draft"]
    draft["products"] = products
    status, saved, _ = json_request(
        api_environment,
        "PATCH",
        f"/api/justificaciones-baja/{justification_id}",
        {"revision": 1, "draft": draft},
    )
    assert status == HTTPStatus.OK
    revision = int(saved["item"]["revision"])

    status, generated, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/costes/generar",
        {"revision": revision},
    )
    assert status == HTTPStatus.OK
    revision = int(generated["item"]["revision"])
    generated_products = generated["item"]["draft"]["products"]
    assert {item["cost_origin"] for item in generated_products} == {"generado"}
    first_id, second_id = (item["line_id"] for item in generated_products)

    status, manual, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/costes/manual",
        {"revision": revision, "line_id": first_id, "manual_unit_cost": "0.55"},
    )
    assert status == HTTPStatus.OK
    revision = int(manual["item"]["revision"])
    first = next(item for item in manual["item"]["draft"]["products"] if item["line_id"] == first_id)
    assert first["cost_origin"] == "manual"
    assert first["manual_unit_cost"] == "0.55"

    status, locked, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/productos/bloqueo",
        {"revision": revision, "line_id": first_id, "locked": True},
    )
    assert status == HTTPStatus.OK
    revision = int(locked["item"]["revision"])
    assert next(
        item for item in locked["item"]["draft"]["products"] if item["line_id"] == first_id
    )["locked"] is True

    status, recalculated, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/costes/recalcular",
        {"revision": revision, "line_ids": [second_id]},
    )
    assert status == HTTPStatus.OK
    revision = int(recalculated["item"]["revision"])

    status, removed, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/costes/retirar-manual",
        {"revision": revision, "line_id": first_id},
    )
    assert status == HTTPStatus.OK
    first = next(item for item in removed["item"]["draft"]["products"] if item["line_id"] == first_id)
    assert first["manual_unit_cost"] is None
    assert first["cost_origin"] == "generado"

    status, detail, _ = json_request(
        api_environment,
        "GET",
        f"/api/justificaciones-baja/{justification_id}",
    )
    assert status == HTTPStatus.OK
    events = {item["event_type"] for item in detail["item"]["history"]}
    assert {
        "costs_generated",
        "manual_cost_set",
        "product_locked",
        "costs_recalculated",
        "manual_cost_removed",
    } <= events


def test_bulk_product_lock_is_one_atomic_revision_and_keeps_line_id_compatibility(
    api_environment: ApiEnvironment,
) -> None:
    created = create_justification(api_environment)
    justification_id = int(created["id"])
    draft = created["draft"]
    draft["products"] = pasted_products(api_environment)
    status, saved, _ = json_request(
        api_environment,
        "PATCH",
        f"/api/justificaciones-baja/{justification_id}",
        {"revision": 1, "draft": draft},
    )
    assert status == HTTPStatus.OK
    revision = int(saved["item"]["revision"])
    line_ids = [item["line_id"] for item in saved["item"]["draft"]["products"]]

    status, locked, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/productos/bloqueo",
        {
            "revision": revision,
            "line_ids": [line_ids[0], line_ids[1], line_ids[0]],
            "locked": True,
        },
    )
    assert status == HTTPStatus.OK
    revision = int(locked["item"]["revision"])
    assert revision == int(saved["item"]["revision"]) + 1
    assert all(item["locked"] is True for item in locked["item"]["draft"]["products"])
    lock_events = [
        event
        for event in locked["item"]["history"]
        if event["event_type"] == "products_locked"
    ]
    assert len(lock_events) == 1
    assert lock_events[0]["metadata"]["line_ids"] == line_ids

    history_size = len(locked["item"]["history"])
    status, invalid, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/productos/bloqueo",
        {
            "revision": revision,
            "line_ids": [line_ids[0], "linea-inexistente"],
            "locked": False,
        },
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert invalid.get("issues")
    status, unchanged, _ = json_request(
        api_environment,
        "GET",
        f"/api/justificaciones-baja/{justification_id}",
    )
    assert status == HTTPStatus.OK
    assert unchanged["item"]["revision"] == revision
    assert len(unchanged["item"]["history"]) == history_size
    assert all(item["locked"] is True for item in unchanged["item"]["draft"]["products"])

    status, legacy, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/productos/bloqueo",
        {"revision": revision, "line_id": line_ids[0], "locked": False},
    )
    assert status == HTTPStatus.OK
    assert legacy["item"]["revision"] == revision + 1
    by_id = {item["line_id"]: item for item in legacy["item"]["draft"]["products"]}
    assert by_id[line_ids[0]]["locked"] is False
    assert by_id[line_ids[1]]["locked"] is True
    assert sum(
        event["event_type"] == "product_unlocked"
        for event in legacy["item"]["history"]
    ) == 1


def test_existing_route_image_is_selected_by_relative_path_and_links_are_rejected(
    api_environment: ApiEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create_justification(api_environment)
    justification_id = int(created["id"])
    image_path = api_environment.licitation_folder / "Mapas" / "ruta.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(png_bytes())

    status, response, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/imagen-ruta",
        {"revision": created["revision"], "relative_path": "Mapas/ruta.png"},
    )
    assert status == HTTPStatus.OK
    metadata = response["item"]["draft"]["route_image"]
    assert metadata["logical_name"] == "ruta.png"
    assert metadata["mime_type"] == "image/png"
    assert metadata["width_px"] == 32
    assert metadata["height_px"] == 18
    assert "relative_path" not in metadata

    status, rejected, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/imagen-ruta",
        {"revision": response["item"]["revision"], "relative_path": "../ruta.png"},
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "ruta" in rejected["error"].lower()

    link = api_environment.licitation_folder / "Mapas" / "enlace.png"
    link.write_bytes(png_bytes())
    original_link_check = api_environment.app._path_component_is_link
    monkeypatch.setattr(
        api_environment.app,
        "_path_component_is_link",
        lambda path: Path(path) == link or original_link_check(path),
    )
    status, linked, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/imagen-ruta",
        {"revision": response["item"]["revision"], "relative_path": "Mapas/enlace.png"},
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "enlace" in linked["error"].lower()


def test_path_link_detection_supports_pre_312_junctions_and_fails_closed(
    api_environment: ApiEnvironment,
) -> None:
    reparse_flag = int(
        getattr(api_environment.app.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    )

    class LegacyJunctionPath:
        def is_symlink(self) -> bool:
            return False

        def lstat(self) -> SimpleNamespace:
            return SimpleNamespace(st_file_attributes=reparse_flag)

    class MissingOutputPath:
        def is_symlink(self) -> bool:
            return False

        def lstat(self) -> SimpleNamespace:
            raise FileNotFoundError

    class UnreadablePath:
        def is_symlink(self) -> bool:
            return False

        def lstat(self) -> SimpleNamespace:
            raise PermissionError

    assert api_environment.app._path_component_is_link(LegacyJunctionPath()) is True
    assert api_environment.app._path_component_is_link(MissingOutputPath()) is False
    assert api_environment.app._path_component_is_link(UnreadablePath()) is True


def test_path_link_detection_prefers_python_312_junction_api(
    api_environment: ApiEnvironment,
) -> None:
    class ModernJunctionPath:
        def is_symlink(self) -> bool:
            return False

        def is_junction(self) -> bool:
            return True

        def lstat(self) -> SimpleNamespace:  # pragma: no cover - must not be reached
            raise AssertionError("No debe consultar atributos tras detectar la unión.")

    assert api_environment.app._path_component_is_link(ModernJunctionPath()) is True


def test_stored_licitation_path_is_checked_before_resolved_folder(
    api_environment: ApiEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create_justification(api_environment)
    justification_id = int(created["id"])
    image_path = api_environment.licitation_folder / "Mapas" / "ruta.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(png_bytes())

    stored_link = api_environment.dropbox_base / "Licitaciones" / "enlace-expediente"
    with api_environment.app.db_session() as conn:
        conn.execute(
            "UPDATE licitaciones SET ruta_carpeta = ? WHERE id = ?",
            ("Licitaciones/enlace-expediente", api_environment.licitacion_id),
        )

    # The resolver fixture deliberately returns the already-resolved real folder.
    # Only the stored lexical path still exposes the simulated junction.
    original_link_check = api_environment.app._path_component_is_link
    monkeypatch.setattr(
        api_environment.app,
        "_path_component_is_link",
        lambda path: Path(path) == stored_link or original_link_check(path),
    )
    status, response, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/imagen-ruta",
        {"revision": created["revision"], "relative_path": "Mapas/ruta.png"},
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "enlace" in response["error"].lower()


def test_stored_licitation_path_keeps_unique_legacy_year_fallback(
    api_environment: ApiEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create_justification(api_environment)
    justification_id = int(created["id"])
    legacy_folder = api_environment.dropbox_base / "2026" / "EXP-LEGACY"
    image_path = legacy_folder / "Mapas" / "ruta.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(png_bytes())
    with api_environment.app.db_session() as conn:
        conn.execute(
            "UPDATE licitaciones SET ruta_carpeta = ? WHERE id = ?",
            ("EXP-LEGACY", api_environment.licitacion_id),
        )

    monkeypatch.setattr(
        api_environment.app,
        "resolve_licitacion_folder",
        lambda row, dropbox_base=None: LicitacionFolderResolution(
            ok=True,
            path=str(legacy_folder.resolve()),
            exists=True,
            inside_dropbox_base=True,
            reason="valid",
            message="Carpeta válida.",
            base_path=str(dropbox_base or api_environment.dropbox_base),
        ),
    )
    status, response, _ = json_request(
        api_environment,
        "POST",
        f"/api/justificaciones-baja/{justification_id}/imagen-ruta",
        {"revision": created["revision"], "relative_path": "Mapas/ruta.png"},
    )
    assert status == HTTPStatus.OK
    assert response["item"]["draft"]["route_image"]["logical_name"] == "ruta.png"


def register_download_document(
    environment: ApiEnvironment,
    justification: dict[str, object],
    *,
    relative_path: str,
    content: bytes,
    generation_number: int,
) -> dict[str, object]:
    file_path = environment.dropbox_base / Path(relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    snapshot_json = canonical_json({"values": {"offer": "20.00", "profit": "2.00"}})
    snapshot_sha256 = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest().upper()
    with environment.app.db_session() as conn:
        repository = JustificationRepository(conn)
        versions = repository.list_versions(int(justification["id"]))
        if versions:
            version = repository.get_version(
                int(justification["id"]),
                version_id=int(versions[0]["id"]),
            )
        else:
            current = repository.get(int(justification["id"]))
            version = repository.freeze(
                int(justification["id"]),
                expected_revision=int(current["revision"]),
                snapshot_json=snapshot_json,
                snapshot_sha256=snapshot_sha256,
                document_context={"route_image": None},
                snapshot_schema_version="v1",
                algorithm_version="v1",
                user_id="admin_test",
                timestamp="2026-07-14T12:10:00",
            )
        return repository.add_document(
            int(justification["id"]),
            version_id=int(version["id"]),
            document_type="word",
            generation_number=generation_number,
            file_name=file_path.name,
            relative_path=Path(relative_path).as_posix(),
            sha256=hashlib.sha256(content).hexdigest().upper(),
            size_bytes=len(content),
            payload_sha256=hashlib.sha256(b"payload").hexdigest().upper(),
            template_version="test-template-v1",
            user_id="admin_test",
            timestamp="2026-07-14T12:11:00",
        )


def freeze_version_for_output_path(
    environment: ApiEnvironment,
    justification: dict[str, object],
    *,
    lot_number: str,
) -> None:
    snapshot_json = canonical_json({"values": {"offer": "20.00", "profit": "2.00"}})
    snapshot_sha256 = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest().upper()
    with environment.app.db_session() as conn:
        repository = JustificationRepository(conn)
        current = repository.get(int(justification["id"]))
        repository.freeze(
            int(justification["id"]),
            expected_revision=int(current["revision"]),
            snapshot_json=snapshot_json,
            snapshot_sha256=snapshot_sha256,
            document_context={
                "identification": {"lot_number": lot_number},
                "route_image": None,
            },
            snapshot_schema_version="v1",
            algorithm_version="v1",
            user_id="admin_test",
            timestamp="2026-07-14T12:10:00",
        )


def test_document_output_uses_frozen_lot_and_a_per_justification_namespace(
    api_environment: ApiEnvironment,
) -> None:
    first = create_justification(api_environment)
    second = create_justification(api_environment)
    freeze_version_for_output_path(api_environment, first, lot_number="LOTE CONGELADO")
    freeze_version_for_output_path(api_environment, second, lot_number="LOTE CONGELADO")
    handler = make_handler(api_environment.app, "POST", "/")

    with api_environment.app.db_session() as conn:
        first_output, first_base = handler._justificacion_output_directory(
            conn, int(first["id"]), 1
        )
        second_output, second_base = handler._justificacion_output_directory(
            conn, int(second["id"]), 1
        )
        conn.execute(
            "UPDATE justificaciones_baja SET lote_numero = 'LOTE MUTADO' WHERE id = ?",
            (int(first["id"]),),
        )
        repeated_output, _ = handler._justificacion_output_directory(
            conn, int(first["id"]), 1
        )

    assert first_base == second_base == api_environment.dropbox_base.resolve()
    assert first_output == repeated_output
    assert "Lote_LOTE_CONGELADO" in first_output.parts
    assert first_output.name == f"Justificacion_{first['id']}"
    assert second_output.name == f"Justificacion_{second['id']}"
    assert first_output != second_output


def test_download_by_opaque_id_checks_role_folder_and_hash(
    api_environment: ApiEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create_justification(api_environment)
    relative = "Licitaciones/EXP-API-2026/Justificaciones/justificacion.docx"
    content = b"valid-docx-content"
    document = register_download_document(
        api_environment,
        created,
        relative_path=relative,
        content=content,
        generation_number=1,
    )
    path = f"/api/justificaciones-baja/documentos/{document['id']}/download"

    for username, role in (("admin_test", "admin"), ("nuria_test", "nuria")):
        handler = make_handler(
            api_environment.app,
            "GET",
            path,
            username=username,
            role=role,
        )
        dispatch(handler, "GET")
        assert handler.responses == []
        assert handler.downloads == [(content, "justificacion.docx", ".docx")]

    file_path = api_environment.dropbox_base / relative
    file_path.write_bytes(b"x" * len(content))
    tampered = make_handler(api_environment.app, "GET", path)
    dispatch(tampered, "GET")
    assert tampered.downloads == []
    assert tampered.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert "hash" in tampered.responses[-1][1]["error"].lower()

    file_path.write_bytes(b"larger-than-the-registered-document")
    original_read_bytes = Path.read_bytes

    def reject_unbounded_document_read(candidate: Path) -> bytes:
        if candidate == file_path:
            raise AssertionError("La descarga no debe usar Path.read_bytes().")
        return original_read_bytes(candidate)

    monkeypatch.setattr(Path, "read_bytes", reject_unbounded_document_read)
    wrong_size = make_handler(api_environment.app, "GET", path)
    dispatch(wrong_size, "GET")
    assert wrong_size.downloads == []
    assert wrong_size.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert "tamaño" in wrong_size.responses[-1][1]["error"].lower()

    foreign_relative = "Otra_licitacion/documento-ajeno.docx"
    foreign_document = register_download_document(
        api_environment,
        created,
        relative_path=foreign_relative,
        content=b"foreign-content",
        generation_number=2,
    )
    foreign = make_handler(
        api_environment.app,
        "GET",
        f"/api/justificaciones-baja/documentos/{foreign_document['id']}/download",
    )
    dispatch(foreign, "GET")
    assert foreign.downloads == []
    assert foreign.responses[-1][0] == HTTPStatus.BAD_REQUEST
    assert "ruta" in foreign.responses[-1][1]["error"].lower()

    missing = make_handler(
        api_environment.app,
        "GET",
        "/api/justificaciones-baja/documentos/999999/download",
    )
    dispatch(missing, "GET")
    assert missing.downloads == []
    assert missing.responses[-1][0] == HTTPStatus.NOT_FOUND
