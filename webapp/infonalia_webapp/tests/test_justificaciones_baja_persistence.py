from __future__ import annotations

import hashlib
import sqlite3

import pytest

from webapp.infonalia_webapp.justificaciones_baja.persistence import (
    JustificationConflictError,
    JustificationNotFoundError,
    JustificationRepository,
    ensure_justificaciones_baja_schema,
)
from webapp.infonalia_webapp.justificaciones_baja.persistence.repository import canonical_json


NOW = "2026-07-14T12:00:00"
USER = "asesoria@example.test"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE licitaciones (
            id INTEGER PRIMARY KEY,
            expediente TEXT NOT NULL,
            objeto TEXT NOT NULL,
            organismo TEXT NOT NULL,
            ruta_carpeta TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY,
            razon_social TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO licitaciones (id, expediente, objeto, organismo, ruta_carpeta)
        VALUES (10, 'EXP-2026-1', 'Suministro de alimentos', 'Ayuntamiento', 'licitaciones/10')
        """
    )
    connection.execute("INSERT INTO clientes (id, razon_social) VALUES (20, 'Cliente de prueba SL')")
    ensure_justificaciones_baja_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def repository(conn: sqlite3.Connection) -> JustificationRepository:
    return JustificationRepository(conn)


def create_justification(
    repository: JustificationRepository,
    *,
    lot: str = "1",
    draft: dict[str, object] | None = None,
) -> dict[str, object]:
    return repository.create(
        licitacion_id=10,
        cliente_id=20,
        expediente="EXP-2026-1",
        lote_numero=lot,
        lote_nombre=f"Lote {lot}",
        draft=draft or {"products": [], "route_image": {"asset_id": None}},
        user_id=USER,
        timestamp=NOW,
    )


def freeze_version(
    repository: JustificationRepository,
    justification: dict[str, object],
    *,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    snapshot_json = canonical_json(
        {
            "schema_version": "justification-snapshot-v1",
            "algorithm_version": "justification-calculation-v1",
            "values": {"offer": "78627.62", "profit": "6783.94"},
        }
    )
    return repository.freeze(
        int(justification["id"]),
        expected_revision=int(justification["revision"]),
        snapshot_json=snapshot_json,
        snapshot_sha256=sha256_text(snapshot_json),
        document_context=context or {"arguments": ["Rutas consolidadas"]},
        snapshot_schema_version="justification-snapshot-v1",
        algorithm_version="justification-calculation-v1",
        user_id=USER,
        timestamp=NOW,
    )


def test_schema_is_idempotent_and_has_foreign_keys_indexes_and_immutable_triggers(
    conn: sqlite3.Connection,
) -> None:
    ensure_justificaciones_baja_schema(conn)

    objects = {
        (row["type"], row["name"])
        for row in conn.execute(
            """
            SELECT type, name FROM sqlite_master
            WHERE name = 'justificaciones_baja'
               OR name LIKE 'justificacion_baja%'
               OR name LIKE 'trg_jb_%'
            """
        ).fetchall()
    }
    assert {
        ("table", "justificaciones_baja"),
        ("table", "justificacion_baja_versiones"),
        ("table", "justificacion_baja_documentos"),
        ("table", "justificacion_baja_assets"),
        ("table", "justificacion_baja_historial"),
        ("trigger", "trg_jb_versiones_no_update"),
        ("trigger", "trg_jb_documentos_no_delete"),
        ("trigger", "trg_jb_assets_no_update"),
        ("trigger", "trg_jb_historial_no_delete"),
    } <= objects
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_create_get_list_and_history_use_canonical_draft(repository: JustificationRepository) -> None:
    created = create_justification(
        repository,
        draft={"z": 1, "a": {"route_asset_id": None}},
    )

    assert created["revision"] == 1
    assert created["estado"] == "borrador"
    assert created["draft"] == {"a": {"route_asset_id": None}, "z": 1}
    assert created["route_image"] is None
    assert created["versions"] == []
    assert created["documents"] == []
    assert created["history"][0]["event_type"] == "created"
    listed = repository.list(licitacion_id=10, cliente_id=20, state="borrador")
    assert [item["id"] for item in listed] == [created["id"]]
    assert "draft" not in listed[0]


def test_create_rolls_back_justification_when_initial_history_insert_fails(
    repository: JustificationRepository,
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        """
        CREATE TRIGGER abort_created_history
        BEFORE INSERT ON justificacion_baja_historial
        WHEN NEW.event_type = 'created'
        BEGIN
            SELECT RAISE(ABORT, 'forced history failure');
        END
        """
    )

    with pytest.raises(sqlite3.IntegrityError, match="forced history failure"):
        create_justification(repository)

    assert conn.execute("SELECT COUNT(*) FROM justificaciones_baja").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM justificacion_baja_historial").fetchone()[0] == 0
    assert repository.list() == []


def test_draft_rejects_embedded_binary_and_base64(repository: JustificationRepository) -> None:
    with pytest.raises(ValueError, match="asset_id"):
        create_justification(repository, draft={"route": {"image_base64": "AAAA"}})
    with pytest.raises(ValueError, match="asset_id"):
        create_justification(repository, draft={"route": "data:image/png;base64,AAAA"})
    with pytest.raises(ValueError, match="asset_id"):
        create_justification(repository, draft={"route": b"binary"})


def test_update_draft_uses_optimistic_revision_and_preserves_failed_write(
    repository: JustificationRepository,
) -> None:
    created = create_justification(repository)
    updated = repository.update_draft(
        int(created["id"]),
        expected_revision=1,
        draft={"products": [{"line_id": "P-1"}]},
        expediente="EXP-2026-1",
        lote_numero="1",
        lote_nombre="Lote 1 revisado",
        profit_raw="6783.94",
        profit_display="6.783,94 €",
        profit_percentage_raw="0.08628",
        profit_percentage_display="8,63 %",
        user_id=USER,
        timestamp=NOW,
    )
    assert updated["revision"] == 2
    assert updated["profit_percentage_display"] == "8,63 %"

    with pytest.raises(JustificationConflictError):
        repository.update_draft(
            int(created["id"]),
            expected_revision=1,
            draft={"products": [{"line_id": "STALE"}]},
            expediente="STALE",
            lote_numero="1",
            lote_nombre="STALE",
            profit_raw=None,
            profit_display=None,
            user_id=USER,
            timestamp=NOW,
        )
    persisted = repository.get(int(created["id"]))
    assert persisted["revision"] == 2
    assert persisted["draft"]["products"][0]["line_id"] == "P-1"


def test_freeze_validates_hash_is_atomic_and_versions_are_append_only(
    repository: JustificationRepository,
    conn: sqlite3.Connection,
) -> None:
    created = create_justification(repository)
    snapshot_json = canonical_json({"values": {"offer": "100.00"}})
    with pytest.raises(ValueError, match="no coincide"):
        repository.freeze(
            int(created["id"]),
            expected_revision=1,
            snapshot_json=snapshot_json,
            snapshot_sha256="0" * 64,
            document_context={},
            snapshot_schema_version="v1",
            algorithm_version="v1",
            user_id=USER,
            timestamp=NOW,
        )
    assert repository.list_versions(int(created["id"])) == []

    version = freeze_version(repository, created)
    assert version["version_number"] == 1
    assert version["document_context"] == {"arguments": ["Rutas consolidadas"]}
    assert version["document_context_sha256"] == sha256_text(
        canonical_json({"arguments": ["Rutas consolidadas"]})
    )
    frozen = repository.get(int(created["id"]))
    assert frozen["draft_frozen"] is True
    assert frozen["revision"] == 2

    with pytest.raises(JustificationConflictError, match="ya está congelada"):
        freeze_version(repository, frozen)
    assert len(repository.list_versions(int(created["id"]))) == 1
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(
            "UPDATE justificacion_baja_versiones SET algorithm_version = 'mutated' WHERE id = ?",
            (version["id"],),
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM justificacion_baja_versiones WHERE id = ?", (version["id"],))


def test_new_draft_can_freeze_same_economic_snapshot_as_new_version(
    repository: JustificationRepository,
) -> None:
    created = create_justification(repository)
    first = freeze_version(repository, created)
    frozen = repository.get(int(created["id"]))
    mutable = repository.update_draft(
        int(created["id"]),
        expected_revision=int(frozen["revision"]),
        draft={"products": [], "narrative_revision": 2},
        expediente="EXP-2026-1",
        lote_numero="1",
        lote_nombre="Lote 1",
        profit_raw="6783.94",
        profit_display="6.783,94 €",
        user_id=USER,
        timestamp=NOW,
    )
    assert mutable["draft_based_on_version"] == 1
    second = freeze_version(repository, mutable, context={"arguments": ["Compra directa"]})

    assert second["version_number"] == 2
    assert second["snapshot_sha256"] == first["snapshot_sha256"]
    assert second["document_context_sha256"] != first["document_context_sha256"]


def test_documents_are_version_bound_versioned_and_immutable(
    repository: JustificationRepository,
    conn: sqlite3.Connection,
) -> None:
    created = create_justification(repository)
    version = freeze_version(repository, created)
    file_hash = sha256_bytes(b"docx bytes")
    payload_hash = sha256_text(canonical_json({"payload": 1}))
    word = repository.add_document(
        int(created["id"]),
        version_id=int(version["id"]),
        document_type="word",
        generation_number=1,
        file_name="justificacion_v1_g1.docx",
        relative_path="justificaciones/1/justificacion_v1_g1.docx",
        sha256=file_hash,
        size_bytes=10,
        snapshot_sha256=str(version["snapshot_sha256"]),
        payload_sha256=payload_hash,
        template_version="word-template-v1",
        user_id=USER,
        timestamp=NOW,
    )
    with pytest.raises(JustificationConflictError, match="hashes documentales"):
        repository.add_document(
            int(created["id"]),
            version_id=int(version["id"]),
            document_type="excel",
            generation_number=1,
            file_name="auditoria_incoherente.xlsx",
            relative_path="justificaciones/1/auditoria_incoherente.xlsx",
            sha256=sha256_bytes(b"wrong xlsx"),
            size_bytes=10,
            payload_sha256=sha256_text("wrong payload"),
            template_version="excel-audit-v1",
            user_id=USER,
            timestamp=NOW,
        )
    excel = repository.add_document(
        int(created["id"]),
        version_id=int(version["id"]),
        document_type="excel",
        generation_number=1,
        file_name="auditoria_v1_g1.xlsx",
        relative_path="justificaciones/1/auditoria_v1_g1.xlsx",
        sha256=sha256_bytes(b"xlsx bytes"),
        size_bytes=10,
        payload_sha256=payload_hash,
        template_version="excel-audit-v1",
        user_id=USER,
        timestamp=NOW,
    )
    assert word["generation_number"] == excel["generation_number"] == 1
    assert word["snapshot_sha256"] == version["snapshot_sha256"]

    opaque = repository.get_document_by_id(int(word["id"]))
    assert opaque["justificacion_id"] == created["id"]
    assert opaque["licitacion_id"] == 10
    assert opaque["relative_path"] == "justificaciones/1/justificacion_v1_g1.docx"
    with pytest.raises(JustificationConflictError):
        repository.add_document(
            int(created["id"]),
            version_id=int(version["id"]),
            document_type="word",
            generation_number=1,
            file_name="duplicate.docx",
            relative_path="justificaciones/1/duplicate.docx",
            sha256=file_hash,
            size_bytes=10,
            payload_sha256=payload_hash,
            template_version="word-template-v1",
            user_id=USER,
            timestamp=NOW,
        )
    with pytest.raises(ValueError, match="ruta relativa segura"):
        repository.add_document(
            int(created["id"]),
            version_id=int(version["id"]),
            document_type="word",
            file_name="escape.docx",
            relative_path="../escape.docx",
            sha256=file_hash,
            size_bytes=10,
            payload_sha256=payload_hash,
            template_version="word-template-v1",
            user_id=USER,
            timestamp=NOW,
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE justificacion_baja_documentos SET file_name = 'x' WHERE id = ?", (word["id"],))


def test_document_cannot_reference_version_from_another_justification(
    repository: JustificationRepository,
) -> None:
    first = create_justification(repository, lot="1")
    second = create_justification(repository, lot="2")
    first_version = freeze_version(repository, first)
    with pytest.raises(JustificationNotFoundError, match="no pertenece"):
        repository.add_document(
            int(second["id"]),
            version_id=int(first_version["id"]),
            document_type="word",
            generation_number=1,
            file_name="wrong.docx",
            relative_path="justificaciones/2/wrong.docx",
            sha256=sha256_bytes(b"wrong"),
            size_bytes=5,
            payload_sha256=sha256_text("payload"),
            template_version="v1",
            user_id=USER,
            timestamp=NOW,
        )
    assert repository.list_documents(int(second["id"])) == []


def test_route_image_is_binary_asset_with_optimistic_traced_replacement(
    repository: JustificationRepository,
    conn: sqlite3.Connection,
) -> None:
    created = create_justification(repository)
    first_bytes = b"\x89PNG\r\nfirst"
    first = repository.put_route_image(
        int(created["id"]),
        expected_revision=1,
        content=first_bytes,
        mime_type="image/png",
        width_px=1200,
        height_px=800,
        file_name="ruta.png",
        user_id=USER,
        timestamp=NOW,
    )
    assert first["content"] == first_bytes
    assert first["sha256"] == sha256_bytes(first_bytes)
    assert first["replaced_asset_id"] is None
    general = repository.get(int(created["id"]))
    assert general["revision"] == 1
    assert general["route_image"]["id"] == first["id"]
    assert "content" not in general["route_image"]
    assert repository.get_route_image(asset_id=int(first["id"]))["content"] == first_bytes

    with pytest.raises(JustificationConflictError):
        repository.put_route_image(
            int(created["id"]),
            expected_revision=0,
            content=b"stale",
            mime_type="image/jpeg",
            width_px=20,
            height_px=10,
            file_name="stale.jpg",
            user_id=USER,
            timestamp=NOW,
        )
    second_bytes = b"\xff\xd8\xffreplacement"
    second = repository.put_route_image(
        int(created["id"]),
        expected_revision=1,
        content=second_bytes,
        mime_type="image/jpeg",
        width_px=1600,
        height_px=900,
        file_name="ruta-2.jpg",
        user_id=USER,
        timestamp="2026-07-14T12:05:00",
    )
    assert second["replaced_asset_id"] == first["id"]
    assert repository.get(int(created["id"]))["route_asset_id"] == second["id"]
    assert repository.get_route_image(asset_id=int(first["id"]))["content"] == first_bytes
    history_types = [item["event_type"] for item in repository.list_history(int(created["id"]))]
    assert "route_image_added" in history_types
    assert "route_image_replaced" in history_types
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM justificacion_baja_assets WHERE id = ?", (first["id"],))


def test_route_image_idempotent_put_does_not_create_replacement(
    repository: JustificationRepository,
) -> None:
    created = create_justification(repository)
    content = b"same-png"
    first = repository.put_route_image(
        int(created["id"]),
        expected_revision=1,
        content=content,
        mime_type="image/png",
        width_px=10,
        height_px=10,
        file_name="same.png",
        user_id=USER,
        timestamp=NOW,
    )
    second = repository.put_route_image(
        int(created["id"]),
        expected_revision=1,
        content=content,
        mime_type="image/png",
        width_px=10,
        height_px=10,
        file_name="same.png",
        user_id=USER,
        timestamp=NOW,
    )
    assert second["id"] == first["id"]
    assert repository.get(int(created["id"]))["revision"] == 1


def test_states_are_limited_and_state_change_is_audited(
    repository: JustificationRepository,
    conn: sqlite3.Connection,
) -> None:
    created = create_justification(repository)
    sent = repository.update_state(
        int(created["id"]),
        expected_revision=1,
        state="enviado_cliente",
        user_id=USER,
        timestamp=NOW,
    )
    final = repository.update_state(
        int(created["id"]),
        expected_revision=2,
        state="final",
        user_id=USER,
        timestamp=NOW,
    )
    assert sent["estado"] == "enviado_cliente"
    assert final["estado"] == "final"
    with pytest.raises(ValueError, match="Estado no válido"):
        repository.update_state(
            int(created["id"]),
            expected_revision=3,
            state="inventado",
            user_id=USER,
            timestamp=NOW,
        )
    history_id = repository.list_history(int(created["id"]))[0]["id"]
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM justificacion_baja_historial WHERE id = ?", (history_id,))


def test_parent_foreign_keys_are_restrictive(repository: JustificationRepository, conn: sqlite3.Connection) -> None:
    create_justification(repository)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute("DELETE FROM clientes WHERE id = 20")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute("DELETE FROM licitaciones WHERE id = 10")
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
