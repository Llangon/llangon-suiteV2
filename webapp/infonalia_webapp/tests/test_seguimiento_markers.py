from __future__ import annotations

import sqlite3
from pathlib import Path

from webapp.infonalia_webapp.seguimiento_markers import (
    FOLLOW_MARKER_NAME,
    allowed_marker_folder,
    create_follow_marker_for_licitacion,
    create_id_marker_for_licitacion,
    ensure_id_marker,
    find_id_markers,
    get_marker_status_for_licitacion,
    is_year_folder,
    iter_monitor_year_roots,
    monitor_year_bounds,
    open_licitacion_folder,
    resolve_marker_folder,
    scan_follow_markers,
    sync_marker_paths,
)
from webapp.infonalia_webapp.monitor.repository import ensure_monitor_schema


def test_year_folder_detection_uses_exact_name_and_configurable_range(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    for name in ["2022", "2026", "2122", "Luisa", "Infonalia", "Resumen licitaciones 2016 a 2021", "99", "202A"]:
        (root / name).mkdir(parents=True)

    assert is_year_folder("2026")
    assert is_year_folder("2122")
    assert not is_year_folder("Luisa")
    assert not is_year_folder("Resumen licitaciones 2016 a 2021")
    assert not is_year_folder("99")
    assert not is_year_folder("202A")
    assert not is_year_folder("1999")
    assert is_year_folder("1999", 1900, 2300)
    assert monitor_year_bounds({"INFONALIA_MONITOR_YEAR_MIN": "2025", "INFONALIA_MONITOR_YEAR_MAX": "2030"}) == (2025, 2030)

    year_roots = [item.name for item in iter_monitor_year_roots(root)]
    assert year_roots == ["2022", "2026", "2122"]
    assert [item.name for item in iter_monitor_year_roots(root, 2025, 2030)] == ["2026"]


def test_ensure_id_marker_creates_exact_empty_file_without_follow_marker(tmp_path: Path) -> None:
    folder = tmp_path / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)

    result = ensure_id_marker(33, folder)

    assert result["ok"] is True
    assert result["created"] is True
    assert (folder / "33.llangon").exists()
    assert (folder / "33.llangon").read_text(encoding="utf-8") == ""
    assert not (folder / "ID_33.llangon").exists()
    assert not (folder / "Lic_33.llangon").exists()
    assert not (folder / FOLLOW_MARKER_NAME).exists()

    (folder / "33.llangon").write_text("manual", encoding="utf-8")
    second = ensure_id_marker(33, folder)
    assert second["created"] is False
    assert (folder / "33.llangon").read_text(encoding="utf-8") == "manual"


def test_scan_markers_only_enters_valid_year_roots_and_recurses_inside(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    valid = root / "2026" / "06 JUNIO" / "no" / "licitacion X"
    ignored_text = root / "Resumen licitaciones 2016 a 2021" / "licitacion"
    ignored_alpha = root / "202A" / "licitacion"
    ignored_short = root / "99" / "licitacion"
    ignored_name = root / "Infonalia" / "licitacion"
    for folder in [valid, ignored_text, ignored_alpha, ignored_short, ignored_name]:
        folder.mkdir(parents=True)
        (folder / "33.llangon").write_text("", encoding="utf-8")
    (valid / FOLLOW_MARKER_NAME).write_text("", encoding="utf-8")
    (valid / "abc.llangon").write_text("", encoding="utf-8")

    records = find_id_markers(root)

    assert len(records) == 1
    assert records[0]["licitacion_id"] == 33
    assert records[0]["folder_path"] == valid
    assert records[0]["follow_marker_exists"] is True
    summary = scan_follow_markers(root)
    assert summary["found"] == 1
    assert summary["following"] == 1


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
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
    return conn


def test_sync_marker_paths_repairs_moved_folder_and_follow_state(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "no" / "licitacion X"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / FOLLOW_MARKER_NAME).write_text("", encoding="utf-8")
    conn = make_conn()
    ensure_monitor_schema(conn)
    conn.execute(
        "INSERT INTO licitaciones (id, expediente, ruta_carpeta, updated_at) VALUES (33, 'EXP-33', '2026/antigua', '')"
    )

    result = sync_marker_paths(
        conn,
        root,
        timestamp="2026-06-17T10:00:00",
        normalize_folder_path=lambda path: str(Path(path).relative_to(root)),
    )

    row = conn.execute("SELECT * FROM licitaciones WHERE id = 33").fetchone()
    assert result["found"] == 1
    assert result["updated"] == 1
    assert result["following"] == 1
    assert Path(row["ruta_carpeta"]).parts == ("2026", "06 JUNIO", "no", "licitacion X")
    assert row["seguimiento_activo"] == 1
    assert row["seguimiento_ultima_sync"] == "2026-06-17T10:00:00"
    assert row["seguimiento_marker_path"].endswith("33.llangon")
    event = conn.execute("SELECT * FROM licitacion_path_reconciliation_events WHERE licitacion_id = 33").fetchone()
    assert event["result"] == "updated"
    assert event["old_path"] == "2026/antigua"
    assert Path(event["new_path"]).parts == ("2026", "06 JUNIO", "no", "licitacion X")


def test_sync_marker_paths_reports_conflicts_without_updating(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder_a = root / "2026" / "A"
    folder_b = root / "2026" / "B"
    folder_multi = root / "2026" / "multi"
    for folder in [folder_a, folder_b, folder_multi]:
        folder.mkdir(parents=True)
    (folder_a / "33.llangon").write_text("", encoding="utf-8")
    (folder_b / "33.llangon").write_text("", encoding="utf-8")
    (folder_multi / "44.llangon").write_text("", encoding="utf-8")
    (folder_multi / "55.llangon").write_text("", encoding="utf-8")
    conn = make_conn()
    ensure_monitor_schema(conn)
    conn.execute("INSERT INTO licitaciones (id, expediente, ruta_carpeta, updated_at) VALUES (33, 'EXP-33', '', '')")
    conn.execute("INSERT INTO licitaciones (id, expediente, ruta_carpeta, updated_at) VALUES (44, 'EXP-44', '', '')")

    result = sync_marker_paths(conn, root, timestamp="2026-06-17T10:00:00")

    assert result["found"] == 4
    assert result["updated"] == 0
    assert {item["type"] for item in result["conflicts"]} == {
        "duplicate_licitacion_marker",
        "folder_multiple_id_markers",
    }
    rows = conn.execute("SELECT id, ruta_carpeta, seguimiento_activo FROM licitaciones ORDER BY id").fetchall()
    assert [(row["id"], row["ruta_carpeta"], row["seguimiento_activo"]) for row in rows] == [
        (33, "", 0),
        (44, "", 0),
    ]
    event_results = conn.execute(
        "SELECT result, reason FROM licitacion_path_reconciliation_events ORDER BY id"
    ).fetchall()
    assert {row["result"] for row in event_results} == {"conflict"}
    assert {row["reason"] for row in event_results} == {
        "duplicate_licitacion_marker",
        "folder_multiple_id_markers",
    }


def test_marker_status_is_derived_from_existing_files(tmp_path: Path) -> None:
    folder = tmp_path / "licitacion"
    folder.mkdir()
    row = {"id": 33, "ruta_carpeta": str(folder), "seguimiento_ultima_sync": "2026-06-17T10:00:00"}

    status_without_markers = get_marker_status_for_licitacion(row)
    assert status_without_markers["activo"] is False
    assert status_without_markers["id_marker_exists"] is False

    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / FOLLOW_MARKER_NAME).write_text("", encoding="utf-8")
    status = get_marker_status_for_licitacion(row)
    assert status["activo"] is True
    assert status["id_marker_exists"] is True
    assert status["follow_marker_exists"] is True
    assert status["warning"] == ""


def test_marker_status_resolves_legacy_relative_path_inside_year_root(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion X"
    folder.mkdir(parents=True)
    (folder / "33.llangon").write_text("", encoding="utf-8")
    (folder / FOLLOW_MARKER_NAME).write_text("", encoding="utf-8")
    row = {"id": 33, "ruta_carpeta": "06 JUNIO/licitacion X"}

    resolved = resolve_marker_folder(row, root)
    status = get_marker_status_for_licitacion(row, root)

    assert resolved == folder
    assert status["folder_exists"] is True
    assert status["activo"] is True
    assert status["follow_marker_exists"] is True


def test_create_marker_helpers_create_exact_files_and_do_not_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "06 JUNIO" / "licitacion"
    folder.mkdir(parents=True)
    row = {"id": 33, "ruta_carpeta": str(folder)}

    id_result = create_id_marker_for_licitacion(row, allowed_roots=[root])
    follow_result = create_follow_marker_for_licitacion(row, allowed_roots=[root])

    assert id_result["ok"] is True
    assert id_result["created"] is True
    assert follow_result["ok"] is True
    assert follow_result["created"] is True
    assert (folder / "33.llangon").is_file()
    assert (folder / FOLLOW_MARKER_NAME).is_file()
    assert not (folder / "[IdLicitacion].llangon").exists()

    (folder / "33.llangon").write_text("manual", encoding="utf-8")
    second = create_id_marker_for_licitacion(row, allowed_roots=[root])

    assert second["ok"] is True
    assert second["created"] is False
    assert second["exists"] is True
    assert (folder / "33.llangon").read_text(encoding="utf-8") == "manual"


def test_create_marker_helpers_reject_missing_and_outside_folders(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    outside = tmp_path / "Outside"
    missing = root / "2026" / "missing"
    outside_folder = outside / "2026" / "licitacion"
    root.mkdir()
    outside_folder.mkdir(parents=True)

    missing_result = create_id_marker_for_licitacion({"id": 33, "ruta_carpeta": str(missing)}, allowed_roots=[root])
    outside_result = create_follow_marker_for_licitacion({"id": 33, "ruta_carpeta": str(outside_folder)}, allowed_roots=[root])

    assert missing_result["ok"] is False
    assert "Carpeta" in missing_result["error"]
    assert outside_result["ok"] is False
    assert "fuera" in outside_result["error"]
    assert not (outside_folder / FOLLOW_MARKER_NAME).exists()


def test_allowed_marker_folder_normalizes_relative_traversal_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    safe_folder = root / "outside"
    root.mkdir()
    safe_folder.mkdir()

    folder, error = allowed_marker_folder(
        {"id": 33, "ruta_carpeta": "../outside"},
        allowed_roots=[root],
        dropbox_root=root,
    )

    assert folder == safe_folder.resolve()
    assert error == ""


def test_open_licitacion_folder_uses_mocked_opener_after_safe_validation(tmp_path: Path) -> None:
    root = tmp_path / "ReplicaDb"
    folder = root / "2026" / "licitacion"
    folder.mkdir(parents=True)
    opened: list[str] = []

    result = open_licitacion_folder(
        {"id": 33, "ruta_carpeta": str(folder)},
        allowed_roots=[root],
        opener=opened.append,
    )

    assert result["ok"] is True
    assert opened == [str(folder.resolve())]
