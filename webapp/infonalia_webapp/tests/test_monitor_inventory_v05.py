from __future__ import annotations

import sqlite3
from pathlib import Path

from webapp.infonalia_webapp.monitor.classification import (
    classify_document,
    classify_folder,
    is_relevant_document,
    is_system_file,
)
from webapp.infonalia_webapp.monitor.document_summary import build_document_summary
from webapp.infonalia_webapp.monitor.inventory import scan_inventory_files
from webapp.infonalia_webapp.document_tree import build_document_tree_payload
from webapp.infonalia_webapp.monitor.repository import ensure_monitor_schema
from webapp.infonalia_webapp.monitor.scanner import MarkerRecord
from webapp.infonalia_webapp.monitor.service import run_monitor
from webapp.infonalia_webapp.tests.test_download_endpoint import make_download_handler
from webapp.infonalia_webapp.tests.test_import_endpoints import load_app_module, temporary_app_database


def make_db(path: Path, rows: list[tuple[int, str]] | None = None) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE licitaciones (
                id INTEGER PRIMARY KEY,
                expediente TEXT,
                ruta_carpeta TEXT,
                seguimiento_activo INTEGER NOT NULL DEFAULT 0,
                seguimiento_ultimo_check TEXT,
                seguimiento_ultima_sync TEXT,
                seguimiento_marker_path TEXT,
                seguimiento_marker_warning TEXT,
                updated_at TEXT
            );
            """
        )
        for licitacion_id, ruta_carpeta in rows or []:
            conn.execute(
                "INSERT INTO licitaciones (id, expediente, ruta_carpeta, updated_at) VALUES (?, ?, ?, '')",
                (licitacion_id, f"EXP-{licitacion_id}", ruta_carpeta),
            )
        conn.commit()
    finally:
        conn.close()


def test_inventory_marks_system_files_and_excludes_markers_from_scan(tmp_path: Path) -> None:
    folder = tmp_path / "licitacion"
    folder.mkdir()
    for name in [
        "33.llangon",
        "EnSeguimiento.llangon",
        "comando_python.txt",
        "desktop.ini",
        "Thumbs.db",
        "~$temporal.docx",
        "descarga.tmp",
        "archivo.crdownload",
        "archivo.part",
        "salida.log",
        "HTTP.url",
        "PCAP contrato.pdf",
    ]:
        (folder / name).write_text("x", encoding="utf-8")

    marker = MarkerRecord(33, folder, folder / "33.llangon")
    files = scan_inventory_files(marker)
    by_name = {item.file_name: item for item in files}

    assert "33.llangon" not in by_name
    assert "EnSeguimiento.llangon" not in by_name
    assert by_name["PCAP contrato.pdf"].is_relevant is True
    for name in [
        "comando_python.txt",
        "desktop.ini",
        "Thumbs.db",
        "~$temporal.docx",
        "descarga.tmp",
        "archivo.crdownload",
        "archivo.part",
        "salida.log",
        "HTTP.url",
    ]:
        assert by_name[name].is_system_file is True
        assert by_name[name].is_relevant is False
    assert by_name["HTTP.url"].file_type == "Enlace"


def test_document_classification_rules() -> None:
    cases = {
        "PCAP contrato.pdf": "PCAP",
        "Pliego tecnico.pdf": "PPT",
        "Licitación.pdf": "Anuncio",
        "DOC_CN_123.pdf": "Anuncio",
        "Anexo I.pdf": "Anexo",
        "Requerimiento subsanacion.pdf": "Requerimiento",
        "Acta mesa.pdf": "Acta",
        "Oferta economica.pdf": "Oferta",
        "Justificante presentacion.pdf": "Oferta",
        "Certificado ISO.pdf": "Certificado",
        "Ficha tecnica producto.pdf": "Ficha tecnica",
        "Documento raro.pdf": "Otro",
    }
    for filename, expected in cases.items():
        assert classify_document(Path(filename), filename) == expected


def test_folder_classification_rules() -> None:
    assert classify_folder(r"Requerimiento\carta.pdf") == "requerimiento"
    assert classify_folder(r"SERVILINE\Documentacion\Sobre 1\doc.pdf") == "sobre_1"
    assert classify_folder(r"SERVILINE\Documentacion\Sobre 2\doc.pdf") == "sobre_2"
    assert classify_folder(r"SERVILINE\Documentacion\Sobre 3\doc.pdf") == "sobre_3"
    assert classify_folder(r"SERVILINE\Recibido 2026 05 08\doc.pdf") == "recibido"
    assert classify_folder(r"Documentacion\doc.pdf") == "documentacion"
    assert classify_folder(r"carpeta normal\doc.pdf") == "otros"


def test_document_summary_counts_relevant_files_and_flags() -> None:
    rows = [
        {
            "licitacion_id": 61,
            "file_type": "PCAP",
            "folder_type": "raiz_licitacion",
            "is_relevant": 1,
            "is_system_file": 0,
            "is_missing": 0,
            "last_seen_at": "2026-06-17T16:44:00",
            "modified_at": "2026-06-17T12:00:00",
        },
        {
            "licitacion_id": 61,
            "file_type": "PPT",
            "folder_type": "raiz_licitacion",
            "is_relevant": 1,
            "is_system_file": 0,
            "is_missing": 0,
            "last_seen_at": "2026-06-17T16:44:00",
            "modified_at": "2026-06-17T13:00:00",
        },
        {
            "licitacion_id": 61,
            "file_type": "Requerimiento",
            "folder_type": "requerimiento",
            "is_relevant": 1,
            "is_system_file": 0,
            "is_missing": 0,
            "last_seen_at": "2026-06-17T16:44:00",
            "modified_at": "2026-06-17T14:00:00",
        },
        {
            "licitacion_id": 61,
            "file_type": "Anexo",
            "folder_type": "otros",
            "is_relevant": 1,
            "is_system_file": 0,
            "is_missing": 0,
            "last_seen_at": "2026-06-17T16:44:00",
            "modified_at": "2026-06-17T15:00:00",
        },
        {
            "licitacion_id": 61,
            "file_type": "Sistema",
            "folder_type": "raiz_licitacion",
            "is_relevant": 0,
            "is_system_file": 1,
            "is_missing": 0,
            "last_seen_at": "2026-06-17T16:44:00",
            "modified_at": "2026-06-17T11:00:00",
        },
    ]

    summary = build_document_summary(61, rows)

    assert summary["total_files"] == 5
    assert summary["relevant_files_count"] == 4
    assert summary["has_pcap"] is True
    assert summary["has_ppt"] is True
    assert summary["has_requirements"] is True
    assert summary["requirement_count"] == 1
    assert summary["annex_count"] == 1
    assert summary["last_file_modified_at"] == "2026-06-17T15:00:00"


def test_inventory_mode_saves_classification_and_dry_run_does_not_write(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / "PCAP contrato.pdf").write_text("pcap", encoding="utf-8")
    (folder / "HTTP.url").write_text("url", encoding="utf-8")
    sobre = folder / "SERVILINE" / "Documentacion" / "Sobre 1"
    sobre.mkdir(parents=True)
    (sobre / "Oferta.pdf").write_text("oferta", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, str(folder))])

    dry_run = run_monitor("inventory", dry_run=True, db_path=db_path, root=root)
    assert dry_run["inventory_files_count"] == 3
    assert dry_run["relevant_files_count"] == 2
    assert dry_run["system_files_count"] == 1
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM licitacion_file_inventory").fetchone()[0] == 0
        run_row = conn.execute(
            "SELECT mode, status, dry_run, inventory_files_count FROM monitor_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert run_row == ("inventory", "completed", 1, 3)
    finally:
        conn.close()

    report = run_monitor("inventory", db_path=db_path, root=root)
    assert report["inventory_files_count"] == 3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT file_name, file_type, folder_type, is_relevant, is_system_file
            FROM licitacion_file_inventory
            WHERE licitacion_id = 33
            ORDER BY relative_path
            """
        ).fetchall()
    finally:
        conn.close()
    by_name = {row["file_name"]: row for row in rows}
    assert by_name["PCAP contrato.pdf"]["file_type"] == "PCAP"
    assert by_name["Oferta.pdf"]["folder_type"] == "sobre_1"
    assert by_name["HTTP.url"]["file_type"] == "Enlace"
    assert by_name["HTTP.url"]["is_relevant"] == 0
    assert by_name["HTTP.url"]["is_system_file"] == 1


def test_inventory_mode_reconciles_route_from_unique_marker_and_tree_reports_it(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion real"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / "PCAP.pdf").write_text("pcap", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, "2026\\ruta antigua inexistente")])

    report = run_monitor("inventory", db_path=db_path, root=root, normalize_folder_path=lambda path: str(Path(path).relative_to(root)))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT ruta_carpeta, seguimiento_marker_warning FROM licitaciones WHERE id = 33").fetchone()
        event = conn.execute("SELECT * FROM licitacion_path_reconciliation_events WHERE licitacion_id = 33 ORDER BY id DESC LIMIT 1").fetchone()
        payload = build_document_tree_payload(conn, 33)
    finally:
        conn.close()

    assert report["route_updates_count"] == 1
    assert Path(row["ruta_carpeta"]).parts == ("2026", "06 JUNIO", "licitacion real")
    assert row["seguimiento_marker_warning"] == ""
    assert event["result"] == "updated"
    assert event["reason"] == "unique_marker_found"
    assert payload["path_reconciled"] is True
    assert "actualizada automáticamente" in payload["path_reconcile_message"]
    assert payload["count"] == 1


def test_inventory_mode_reconciles_legacy_month_route_to_year_month_marker(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "07 JULIO" / "licitacion real"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, "07 JULIO\\licitacion real")])

    report = run_monitor("inventory", db_path=db_path, root=root, normalize_folder_path=lambda path: str(Path(path).relative_to(root)))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT ruta_carpeta, seguimiento_marker_warning FROM licitaciones WHERE id = 33").fetchone()
        event = conn.execute("SELECT * FROM licitacion_path_reconciliation_events WHERE licitacion_id = 33 ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()

    assert report["route_updates_count"] == 1
    assert Path(row["ruta_carpeta"]).parts == ("2026", "07 JULIO", "licitacion real")
    assert row["seguimiento_marker_warning"] == ""
    assert event["old_path"] == "07 JULIO\\licitacion real"
    assert Path(event["new_path"]).parts == ("2026", "07 JULIO", "licitacion real")


def test_inventory_mode_does_not_update_duplicate_marker_conflict(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder_a = root / "2026" / "A"
    folder_b = root / "2026" / "B"
    folder_a.mkdir(parents=True)
    folder_b.mkdir(parents=True)
    (folder_a / "33.llangon").write_text("", encoding="utf-8")
    (folder_b / "33.llangon").write_text("", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, "2026\\ruta original")])

    report = run_monitor("inventory", db_path=db_path, root=root, normalize_folder_path=lambda path: str(Path(path).relative_to(root)))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT ruta_carpeta, seguimiento_marker_warning FROM licitaciones WHERE id = 33").fetchone()
        event = conn.execute("SELECT * FROM licitacion_path_reconciliation_events WHERE licitacion_id = 33 ORDER BY id DESC LIMIT 1").fetchone()
        payload = build_document_tree_payload(conn, 33)
    finally:
        conn.close()

    assert report["route_updates_count"] == 0
    assert row["ruta_carpeta"] == "2026\\ruta original"
    assert "Conflicto de marcadores" in row["seguimiento_marker_warning"]
    assert event["result"] == "conflict"
    assert payload["root_status"] == "marker_conflict"
    assert "Conflicto de marcadores" in payload["message"]


def test_inventory_mode_records_missing_folder_without_marker_without_route_change(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    (root / "2026").mkdir(parents=True)
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, "2026\\carpeta inexistente")])

    report = run_monitor("inventory", db_path=db_path, root=root, normalize_folder_path=lambda path: str(Path(path).relative_to(root)))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT ruta_carpeta, seguimiento_marker_warning FROM licitaciones WHERE id = 33").fetchone()
        event = conn.execute("SELECT * FROM licitacion_path_reconciliation_events WHERE licitacion_id = 33 ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()

    assert report["route_updates_count"] == 0
    assert row["ruta_carpeta"] == "2026\\carpeta inexistente"
    assert row["seguimiento_marker_warning"] == "Carpeta no encontrada y sin marcador localizable."
    assert event["result"] == "not_found"
    assert event["reason"] == "folder_missing_without_marker"
    assert "C:\\ReplicaDb" not in (event["old_path"] or "")
    assert '"normalized_path": "2026\\\\carpeta inexistente"' in event["details_json"]
    assert '"reason": "missing_after_normalization"' in event["details_json"]


def test_inventory_mode_normalizes_absolute_dropbox_route_once(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "07 JULIO" / "licitacion real"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, str(folder))])

    first = run_monitor("inventory", db_path=db_path, root=root)
    second = run_monitor("inventory", db_path=db_path, root=root)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT ruta_carpeta FROM licitaciones WHERE id = 33").fetchone()
        updated_events = conn.execute(
            """
            SELECT COUNT(*) FROM licitacion_path_reconciliation_events
            WHERE licitacion_id = 33 AND result = 'updated'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert first["route_updates_count"] == 1
    assert second["route_updates_count"] == 0
    assert Path(row["ruta_carpeta"]).parts == ("2026", "07 JULIO", "licitacion real")
    assert updated_events == 1


def test_inventory_mode_is_idempotent_for_persistent_missing_folder_warning(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    (root / "2026").mkdir(parents=True)
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, "2026\\carpeta inexistente")])

    first = run_monitor("inventory", db_path=db_path, root=root)
    second = run_monitor("inventory", db_path=db_path, root=root)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT ruta_carpeta, seguimiento_marker_warning, updated_at FROM licitaciones WHERE id = 33"
        ).fetchone()
        not_found_events = conn.execute(
            """
            SELECT COUNT(*) FROM licitacion_path_reconciliation_events
            WHERE licitacion_id = 33 AND result = 'not_found'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert first["route_updates_count"] == 0
    assert second["route_updates_count"] == 0
    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert first["warnings"] == second["warnings"]
    assert row["ruta_carpeta"] == "2026\\carpeta inexistente"
    assert row["seguimiento_marker_warning"] == "Carpeta no encontrada y sin marcador localizable."
    assert not_found_events == 1


def test_document_tree_payload_uses_inventory_as_folder_tree(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / "PCAP contrato.pdf").write_text("pcap", encoding="utf-8")
    sub = folder / "Requerimiento"
    sub.mkdir()
    (sub / "Carta requerimiento.pdf").write_text("req", encoding="utf-8")
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, str(folder))])
    run_monitor("inventory", db_path=db_path, root=root)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_monitor_schema(conn)
        payload = build_document_tree_payload(conn, 33)
    finally:
        conn.close()

    assert payload["ok"] is True
    assert payload["source"] == "inventory"
    assert payload["count"] == 2
    names = [node["name"] for node in payload["tree"]]
    assert "PCAP contrato.pdf" in names
    folder_node = next(node for node in payload["tree"] if node["name"] == "Requerimiento")
    assert folder_node["type"] == "folder"
    assert folder_node["children"][0]["name"] == "Carta requerimiento.pdf"
    assert "absolute_path" not in folder_node["children"][0]


def test_document_tree_rejects_traversal_inventory_rows(tmp_path: Path) -> None:
    folder = tmp_path / "licitacion"
    folder.mkdir()
    db_path = tmp_path / "infonalia.db"
    make_db(db_path, [(33, str(folder))])
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_monitor_schema(conn)
        conn.execute(
            """
            INSERT INTO licitacion_file_inventory (
                licitacion_id, folder_path, relative_path, file_name, extension,
                file_type, folder_type, is_relevant, is_system_file, size_bytes,
                modified_at, discovered_at, last_seen_at, source
            )
            VALUES (33, ?, '..\\secreto.pdf', 'secreto.pdf', '.pdf',
                    'Otro', 'otros', 1, 0, 4,
                    '2026-06-17T12:00:00', '2026-06-17T12:00:00',
                    '2026-06-17T12:00:00', 'local_dropbox')
            """,
            (str(folder),),
        )
        payload = build_document_tree_payload(conn, 33)
    finally:
        conn.close()

    assert payload["ok"] is True
    assert payload["count"] == 0
    assert payload["tree"] == []


def test_document_tree_endpoint_returns_controlled_empty_state(tmp_path: Path) -> None:
    app = load_app_module()
    folder = tmp_path / "docs"
    folder.mkdir()
    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, provincia, fecha_limite,
                    hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
                )
                VALUES (33, 'EXP-33', 'Objeto', 'Org', 'Madrid', '2026-06-30',
                        '12:00', 'https://example.test', 'Importada', ?,
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """,
                (str(folder),),
            )
        handler = make_download_handler(app, path="/api/licitaciones/33/document-tree")
        handler.do_GET()

    status, payload = handler.responses[-1]
    assert status == 200
    assert payload["ok"] is True
    assert payload["count"] == 0
    assert payload["tree"] == []
    assert "No hay documentación inventariada" in payload["message"]


def test_licitacion_detail_uses_inventory_summary_and_visible_groups(tmp_path: Path, monkeypatch) -> None:
    app = load_app_module()
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / "PCAP contrato.pdf").write_text("pcap", encoding="utf-8")
    (folder / "HTTP.url").write_text("url", encoding="utf-8")
    req = folder / "Requerimiento"
    req.mkdir()
    (req / "Carta de requerimiento.pdf").write_text("req", encoding="utf-8")
    monkeypatch.setenv("INFONALIA_MONITOR_ROOT", str(root))

    with temporary_app_database(app):
        with app.db_session() as conn:
            conn.execute(
                """
                INSERT INTO licitaciones (
                    id, expediente, objeto, organismo, provincia, fecha_limite,
                    hora_limite, enlace_perfil, estado, ruta_carpeta, created_at, updated_at
                )
                VALUES (33, 'EXP-33', 'Objeto', 'Org', 'Madrid', '2026-06-30',
                        '12:00', 'https://example.test', 'Importada', ?,
                        '2026-06-17T10:00:00', '2026-06-17T10:00:00')
                """,
                (str(folder),),
            )
        run_monitor("inventory", db_path=app.DB_PATH, root=root)
        handler = make_download_handler(app, path="/api/licitaciones/33")
        handler.do_GET()

    status, payload = handler.responses[-1]
    item = payload["item"]
    assert status == 200
    assert item["document_summary"]["total_files"] == 3
    assert item["document_summary"]["relevant_files_count"] == 2
    assert item["document_summary"]["system_files_count"] == 1
    assert item["document_summary"]["has_pcap"] is True
    assert item["document_summary"]["requirement_count"] == 1
    assert [doc["name"] for doc in item["documentos"]] == ["PCAP contrato.pdf", "Carta de requerimiento.pdf"]
    assert all(doc["file_type"] != "Enlace" for doc in item["documentos"])
    assert {group["name"] for group in item["document_groups"]} == {"Documentos principales", "Requerimientos"}


def test_static_detail_ui_hides_inventory_specific_summary_and_groups() -> None:
    script = Path("webapp/infonalia_webapp/static/app.js").read_text(encoding="utf-8")
    documents_render = script.split("function renderLicitacionDocuments", 1)[1].split("function renderLicitacionTracking", 1)[0]

    assert "documentCountLabel" in script
    assert "document_groups" not in script
    assert "renderDocumentSummary(item)" not in documents_render
    assert "item.document_groups" not in documents_render
    assert "Último inventario" not in script
    assert "Sin documentación inventariada" not in script
    assert "Ficheros técnicos" not in script


def test_static_detail_ui_uses_header_actions_and_document_tree() -> None:
    script = Path("webapp/infonalia_webapp/static/app.js").read_text(encoding="utf-8")
    detail_render = script.split("function renderLicitacionDetailView", 1)[1].split("function renderDetailActionBar", 1)[0]
    summary_tab = detail_render.split('data-detail-tab-panel="resumen"', 1)[1].split('data-detail-tab-panel="documentos-seguimiento"', 1)[0]
    docs_tab = detail_render.split('data-detail-tab-panel="documentos-seguimiento"', 1)[1].split('data-detail-tab-panel="ai"', 1)[0]

    assert "renderDetailActionBar(item)" in detail_render
    assert "detail-action-bar" not in summary_tab
    assert "renderDocumentosTabActions(item, folder)" in docs_tab
    assert "renderFolderPanel(item, folder, folderLabel)" in docs_tab
    assert "renderLicitacionTrackingSummary(item)" in docs_tab
    assert "renderLicitacionHistory(item)" in docs_tab
    assert "data-document-tree-panel" in docs_tab
    assert "renderLicitacionDocuments(item)" not in docs_tab
    assert "/document-tree" in script
