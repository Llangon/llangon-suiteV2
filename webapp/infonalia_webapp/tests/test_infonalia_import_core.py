from __future__ import annotations

import html
import hashlib
import imaplib
import json
import socket
import sqlite3
import sys
from email.message import EmailMessage
from pathlib import Path

import pytest

from webapp.infonalia_webapp.infonalia_corpus_harness import (
    MANIFEST_FIELDS,
    extract_msg_fixture,
    load_manifest,
    run_corpus_simulation,
)
from webapp.infonalia_webapp.infonalia_import_core import (
    comparison_value,
    normalize_url,
    reconcile_message,
)
from webapp.infonalia_webapp.infonalia_mail_importer import (
    EXPECTED_FROM,
    EXPECTED_SUBJECT,
    InfonaliaImportConfig,
    import_parsed_email,
    parse_infonalia_email,
    process_mailbox_once,
)
from webapp.infonalia_webapp.tests.test_import_endpoints import (
    PRODUCTIVE_DB_PATH,
    load_app_module,
    temporary_app_database,
)
from webapp.infonalia_webapp.tests.test_infonalia_mail_importer import FakeIMAP


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "infonalia"
MANIFEST_PATH = FIXTURE_ROOT / "infonalia_expected_manifest.json"
REAL_CORPUS_ROOT = FIXTURE_ROOT / "corpus_real_20260720"
REAL_CORPUS_MANIFEST_PATH = REAL_CORPUS_ROOT / "infonalia_expected_manifest.json"
RAW_MSG_SAMPLE_NAMES = (
    "LICITACIONES - Envío de Novedades - 149022 (27).msg",
    "LICITACIONES - Envío de Novedades - 149022 (26).msg",
)


@pytest.fixture(autouse=True)
def isolated_importer_test(monkeypatch: pytest.MonkeyPatch):
    original_connect = sqlite3.connect

    def guarded_connect(database, *args, **kwargs):
        if not isinstance(database, int) and Path(str(database)).resolve() == PRODUCTIVE_DB_PATH.resolve():
            raise AssertionError("Una prueba intentó abrir la SQLite real.")
        if "dropbox" in str(database).casefold():
            raise AssertionError("Una prueba intentó usar una ruta Dropbox.")
        return original_connect(database, *args, **kwargs)

    def blocked_network(*_args, **_kwargs):
        raise AssertionError("Las conexiones de red reales están bloqueadas en estas pruebas.")

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", blocked_network)
    monkeypatch.setattr(imaplib, "IMAP4_SSL", blocked_network)
    monkeypatch.setenv("LLANGON_TESTING", "1")


def block_text(
    *,
    ref: str = "2026103762",
    expediente: str = "CONTR 2026 0000264070",
    objeto: str = "Suministro de avituallamiento para zona norte de Almería - INFOCA.",
    profile: str = "https://www.juntadeandalucia.es/perfil?idExpediente=980549",
    extra_lines: str = "",
) -> str:
    return f"""
Ref. Infonalia: {ref}
Nº Expediente: {expediente}
{extra_lines}
Organismo: AGENCIA DE SEGURIDAD Y GESTIÓN INTEGRAL DE EMERGENCIAS DE ANDALUCÍA (ASEMA)
Resumen del Objeto: {objeto}
Provincia de Ejecución: Almería
Presupuesto: 10.500,00 € Importe sin impuestos
Plazo Presentación: Hasta el próximo día 30/07/26
Ver el texto íntegro del anuncio: https://www.infonalia.es/licitaciones0726/{ref}.pdf
Perfil del Contratante (Pliegos): {profile}
Información extraída del PJA - Plataforma de Contratación de la Junta de Andalucía Número: ----- del día 17/07/26
______________________________________________________________________________________________________________________
"""


def html_from_text(text: str) -> str:
    return "<html><body>" + "<br>".join(html.escape(line) for line in text.splitlines()) + "</body></html>"


def reconcile_same(text: str):
    return reconcile_message(plain_text=text, html_text=html_from_text(text), message_id="<strict@example.test>")


def test_id_expediente_url_and_object_word_never_modify_expediente() -> None:
    text = block_text(objeto="Este expediente incluye varios expedientes auxiliares.")
    result = reconcile_same(text)

    assert result.safe_to_persist is True
    assert result.canonical_blocks[0].expediente == "CONTR 2026 0000264070"
    assert "idExpediente=980549" in result.canonical_blocks[0].url_perfil_contratante


def test_url_with_colons_query_fragment_is_not_split_as_a_business_field() -> None:
    profile = "https://example.test:8443/perfil:ruta?x=1&idExpediente=77&next=https://a.test/#fragmento"
    result = reconcile_same(block_text(profile=profile))

    assert result.safe_to_persist is True
    assert result.canonical_blocks[0].url_perfil_contratante == profile
    assert result.canonical_blocks[0].expediente == "CONTR 2026 0000264070"


def test_nested_html_nbsp_and_split_label_nodes_are_parsed_structurally() -> None:
    plain = block_text()
    nested = """
    <html><body><div><span>Ref.</span><span>&nbsp;Infonalia:</span><b>2026103762</b><br>
    <span>Nº</span><span>&nbsp;Expediente:</span><b>CONTR&nbsp; 2026 0000264070</b><br>
    <span>Organismo:</span><b>AGENCIA DE SEGURIDAD Y GESTIÓN INTEGRAL DE EMERGENCIAS DE ANDALUCÍA (ASEMA)</b><br>
    <span>Resumen del Objeto:</span><b>Suministro de avituallamiento para zona norte de Almería - INFOCA.</b><br>
    <span>Provincia de Ejecución:</span><b>Almería</b><br><span>Presupuesto:</span><b>10.500,00 € Importe sin impuestos</b><br>
    <span>Plazo Presentación:</span><b>Hasta el próximo día 30/07/26</b><br>
    <span>Ver el texto íntegro del anuncio:</span><a href="https://www.infonalia.es/licitaciones0726/2026103762.pdf">www.infonalia.es/licitaciones0726/2026103762.pdf</a><br>
    <span>Perfil del Contratante (Pliegos):</span><a href="https://www.juntadeandalucia.es/perfil?idExpediente=980549">www.juntadeandalucia.es/perfil?idExpediente=980549</a><br>
    <span>Información extraída del</span><b>PJA - Plataforma de Contratación de la Junta de Andalucía Número: ----- del día 17/07/26</b>
    </div></body></html>
    """
    result = reconcile_message(plain_text=plain, html_text=nested)

    assert result.safe_to_persist is True
    assert result.html.marker_count == 1


def test_duplicate_same_field_warns_but_conflicting_or_empty_duplicate_blocks() -> None:
    same = reconcile_same(block_text(extra_lines="Nº Expediente: CONTR 2026 0000264070"))
    conflict = reconcile_same(block_text(extra_lines="Nº Expediente: DISTINTO"))
    empty = reconcile_same(block_text(extra_lines="Nº Expediente:"))

    assert same.safe_to_persist is True
    assert any(item.code == "duplicate_same_value" for item in same.warnings)
    assert conflict.safe_to_persist is False
    assert any(item.code == "conflicting_field" for item in conflict.issues)
    assert empty.safe_to_persist is False
    assert any(item.code == "duplicate_empty_value" for item in empty.issues)


def test_missing_ref_is_not_a_block_and_truncated_ref_is_quarantined() -> None:
    without_ref = block_text().replace("Ref. Infonalia: 2026103762", "Referencia informativa: 2026103762")
    truncated = "Ref. Infonalia: 2026103762\nNº Expediente: EXP-1"

    no_block = reconcile_same(without_ref)
    incomplete = reconcile_same(truncated)

    assert no_block.detected_count == 0
    assert no_block.safe_to_persist is False
    assert incomplete.detected_count == 1
    assert incomplete.quarantine_count == 1
    assert incomplete.safe_to_persist is False


def test_html_text_count_and_reference_disagreements_are_blocking_and_explicit() -> None:
    first = block_text()
    second = block_text(ref="2026103763", expediente="CONTR 2026 0000264400")
    count_mismatch = reconcile_message(plain_text=first, html_text=html_from_text(first + second))
    ref_mismatch = reconcile_message(
        plain_text=first,
        html_text=html_from_text(block_text(ref="2026103764", expediente="CONTR 2026 0000264070")),
    )

    assert count_mismatch.safe_to_persist is False
    assert any(item.code == "block_count_mismatch" and "Texto=1" in item.message for item in count_mismatch.issues)
    assert ref_mismatch.safe_to_persist is False
    assert any(item.code == "reference_order_mismatch" for item in ref_mismatch.issues)


def test_duplicate_ref_inside_message_is_conflict_and_no_consta_is_explicit_value() -> None:
    duplicated = reconcile_same(block_text() + block_text(expediente="OTRO"))
    no_consta = reconcile_same(block_text(expediente="No consta"))

    assert duplicated.safe_to_persist is False
    assert any(item.code == "duplicate_ref_in_message" for item in duplicated.issues)
    assert no_consta.safe_to_persist is True
    assert no_consta.canonical_blocks[0].expediente == "No consta"


def test_malformed_html_is_accepted_only_when_dom_result_reconciles() -> None:
    plain = block_text()
    recoverable = html_from_text(plain).replace("</body></html>", "")
    insufficient = "<html><body><b>Ref. Infonalia:</b>2026103762"

    assert reconcile_message(plain_text=plain, html_text=recoverable).safe_to_persist is True
    failed = reconcile_message(plain_text=plain, html_text=insufficient)
    assert failed.safe_to_persist is False
    assert failed.html.marker_count == 1


def test_values_containing_label_names_do_not_create_fields() -> None:
    text = block_text(
        objeto="Organismo: interno; Presupuesto: estimado; Nº Expediente: citado dentro del objeto.",
    )
    result = reconcile_same(text)

    assert result.safe_to_persist is True
    assert result.canonical_blocks[0].organismo.startswith("AGENCIA DE SEGURIDAD")
    assert result.canonical_blocks[0].expediente == "CONTR 2026 0000264070"


def _render_manifest_block(block: dict[str, object]) -> tuple[str, str]:
    ref = str(block["ref_infonalia"])
    profile = normalize_url(block["perfil_contratante"])
    pdf = f"https://www.infonalia.es/licitaciones0726/{ref}.pdf"
    lines = [
        f"Ref. Infonalia: {ref}",
        f"Nº Expediente: {block['expediente']}",
        f"Organismo: {block['organismo']}",
        f"Resumen del Objeto: {block['resumen_objeto']}",
        f"Provincia de Ejecución: {block['provincia_ejecucion']}",
        f"Presupuesto: {block['presupuesto']}",
        f"Plazo Presentación: {block['plazo_presentacion']}",
        f"Ver el texto íntegro del anuncio: {pdf}",
        f"Perfil del Contratante (Pliegos): {profile}",
        str(block["fuente_informacion"]),
        "_" * 118,
    ]
    plain = "\n".join(lines)
    html_lines = [
        f"<span>{html.escape(line.split(':', 1)[0])}:</span><span>{html.escape(line.split(':', 1)[1])}</span>"
        if ":" in line and not line.startswith(("http", "_"))
        else html.escape(line)
        for line in lines
    ]
    return plain, "<html><body>" + "<br>".join(html_lines) + "</body></html>"


def test_manifest_oracle_drives_396_reconciled_blocks_and_31_duplicates(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST_PATH)
    refs: list[str] = []
    id_expediente_refs: list[str] = []
    text_blocks = html_blocks = 0
    target_expedientes: dict[str, str] = {}

    for expected_file in manifest["files"]:
        plain_parts: list[str] = []
        html_parts: list[str] = []
        for block in expected_file["blocks"]:
            plain, html_body = _render_manifest_block(block)
            plain_parts.append(plain)
            html_parts.append(html_body.removeprefix("<html><body>").removesuffix("</body></html>"))
        result = reconcile_message(
            plain_text="\n".join(plain_parts),
            html_text="<html><body>" + "<br>".join(html_parts) + "</body></html>",
            message_id=str(expected_file["file"]),
        )
        assert result.safe_to_persist, [issue.message for issue in result.issues]
        text_blocks += result.text.marker_count
        html_blocks += result.html.marker_count
        for parsed in result.canonical_blocks:
            refs.append(parsed.ref_infonalia)
            if "idexpediente=" in parsed.url_perfil_contratante.casefold():
                id_expediente_refs.append(parsed.ref_infonalia)
            if parsed.ref_infonalia in {"2026103762", "2026103763"}:
                target_expedientes[parsed.ref_infonalia] = parsed.expediente

    aggregate = manifest["aggregate"]
    assert len(manifest["files"]) == 39
    assert text_blocks == html_blocks == len(refs) == aggregate["block_occurrences"] == 396
    assert len(set(refs)) == aggregate["unique_ref_infonalia"] == 365
    assert len(refs) - len(set(refs)) == aggregate["duplicate_occurrences"] == 31
    assert len(id_expediente_refs) == aggregate["block_occurrences_with_idExpediente_profile_url"] == 25
    assert len(set(id_expediente_refs)) == aggregate["unique_refs_with_idExpediente_profile_url"] == 20
    assert target_expedientes == {
        "2026103762": "CONTR 2026 0000264070",
        "2026103763": "CONTR 2026 0000264400",
    }

    db_path = tmp_path / "isolated.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE refs (ref TEXT PRIMARY KEY)")
        inserted = duplicates = 0
        for ref in refs:
            try:
                conn.execute("INSERT INTO refs(ref) VALUES (?)", (ref,))
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        conn.commit()
    finally:
        conn.close()
    assert (inserted, duplicates) == (365, 31)


def test_corpus_harness_fails_closed_when_msg_fixtures_are_missing(tmp_path: Path) -> None:
    report = run_corpus_simulation(corpus_dir=tmp_path, manifest_path=MANIFEST_PATH)

    assert report["ok"] is False
    assert len(report["missing_files"]) == 39
    assert report["actual"]["msg_files"] == 0
    assert all(value == 0 for value in report["external_effects"].values())


@pytest.mark.parametrize("file_name", RAW_MSG_SAMPLE_NAMES)
def test_real_msg_sample_matches_manifest(file_name: str) -> None:
    manifest = load_manifest(REAL_CORPUS_MANIFEST_PATH)
    expected = next(item for item in manifest["files"] if item["file"] == file_name)
    msg_path = REAL_CORPUS_ROOT / file_name

    assert hashlib.sha256(msg_path.read_bytes()).hexdigest() == expected["sha256_msg"]
    extracted = extract_msg_fixture(msg_path)
    result = reconcile_message(
        plain_text=str(extracted["plain"]),
        html_text=str(extracted["html"]),
        message_id=str(extracted["message_id"]),
    )

    assert result.safe_to_persist is True, result.differences
    assert result.text.marker_count == result.html.marker_count == expected["expected_block_count"]
    assert len(result.canonical_blocks) == len(expected["blocks"])
    for expected_block, actual_block in zip(expected["blocks"], result.canonical_blocks):
        assert actual_block.ordinal == expected_block["ordinal"]
        for expected_name, actual_name in MANIFEST_FIELDS.items():
            expected_value = comparison_value(actual_name, expected_block.get(expected_name, ""))
            actual_value = comparison_value(actual_name, getattr(actual_block, actual_name))
            assert actual_value == expected_value, (
                f"{file_name}, bloque {actual_block.ordinal}, campo {expected_name}"
            )


def strict_raw(*, plain: str, html_body: str, message_id: str = "<strict-mail@example.test>") -> bytes:
    message = EmailMessage()
    message["Subject"] = EXPECTED_SUBJECT
    message["From"] = EXPECTED_FROM
    message["To"] = "test@example.test"
    message["Date"] = "Mon, 20 Jul 2026 13:04:18 +0200"
    message["Message-ID"] = message_id
    message.set_content(plain)
    message.add_alternative(html_body, subtype="html")
    return message.as_bytes()


def strict_config() -> InfonaliaImportConfig:
    return InfonaliaImportConfig(
        enabled=True,
        host="blocked.example.test",
        port=993,
        user="test@example.test",
        password="test-only",
        folder="LLANGON_INFONALIA_TEST",
        expected_from=EXPECTED_FROM,
        expected_subject=EXPECTED_SUBJECT,
        notify_email="admin@example.test",
        mark_read_on_success=True,
        test_forwarders=[],
        lookback_hours=24 * 365,
        strict_mode=True,
    )


def test_strict_mailbox_quarantines_mismatch_without_seen_and_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    raw = strict_raw(plain=block_text(), html_body=html_from_text(block_text() + block_text(ref="2026103763")))
    fake = FakeIMAP({b"1": {"seen": False, "raw": raw}})
    sent: list[str] = []
    with temporary_app_database(app):
        result = process_mailbox_once(
            config=strict_config(),
            imap_factory=lambda *_a, **_k: fake,
            notification_sender=lambda *_a: sent.append("incident") or ("2026-07-20T13:05:00", None),
        )
        with app.db_session() as conn:
            audit = conn.execute("SELECT * FROM infonalia_email_imports ORDER BY id DESC LIMIT 1").fetchone()
            blocks = conn.execute("SELECT result_status FROM infonalia_email_import_blocks ORDER BY ordinal").fetchall()
            licitaciones = conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0]

    assert result["quarantined"] == 2
    assert result["errors"] == 1
    assert fake.messages[b"1"]["seen"] is False
    assert fake.store_calls == []
    assert licitaciones == 0
    assert audit["status"] == "quarantined"
    assert audit["committed"] == 0
    assert len(blocks) == 2
    assert sent == ["incident"]


def test_strict_mailbox_success_seen_and_second_run_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    raw = strict_raw(plain=block_text(), html_body=html_from_text(block_text()))
    monkeypatch.setattr(app, "find_pdftotext", lambda: None)

    with temporary_app_database(app):
        first_fake = FakeIMAP({b"1": {"seen": False, "raw": raw}})
        first = process_mailbox_once(config=strict_config(), imap_factory=lambda *_a, **_k: first_fake, notification_sender=None)
        second_fake = FakeIMAP({b"1": {"seen": False, "raw": raw}})
        second = process_mailbox_once(config=strict_config(), imap_factory=lambda *_a, **_k: second_fake, notification_sender=None)
        with app.db_session() as conn:
            count = conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0]
            audit = conn.execute("SELECT status, marked_seen FROM infonalia_email_imports ORDER BY id").fetchall()

    assert first["imported"] == 1
    assert second["imported"] == 0 and second["duplicates"] == 1
    assert first_fake.messages[b"1"]["seen"] is True
    assert second_fake.messages[b"1"]["seen"] is True
    assert count == 1
    assert all(row["marked_seen"] == 1 for row in audit)


def test_commit_then_seen_failure_is_audited_and_retry_does_not_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    raw = strict_raw(
        plain=block_text(),
        html_body=html_from_text(block_text()),
        message_id="<seen-retry@example.test>",
    )
    monkeypatch.setattr(app, "find_pdftotext", lambda: None)

    class FailingSeenIMAP(FakeIMAP):
        def uid(self, command, *args):
            if str(command).upper() == "STORE":
                self.calls.append(("STORE", args))
                self.store_calls.append((args[0], args[1:]))
                return "NO", [b"simulated"]
            return super().uid(command, *args)

    with temporary_app_database(app):
        failed_fake = FailingSeenIMAP({b"1": {"seen": False, "raw": raw}})
        first = process_mailbox_once(
            config=strict_config(),
            imap_factory=lambda *_a, **_k: failed_fake,
            notification_sender=None,
        )
        with app.db_session() as conn:
            committed = conn.execute(
                "SELECT status, committed, marked_seen FROM infonalia_email_imports ORDER BY id LIMIT 1"
            ).fetchone()
            open_incident = conn.execute(
                "SELECT status FROM infonalia_email_import_incidents WHERE dedupe_key = ?",
                ("seen:<seen-retry@example.test>",),
            ).fetchone()

        retry_fake = FakeIMAP({b"1": {"seen": False, "raw": raw}})
        second = process_mailbox_once(
            config=strict_config(),
            imap_factory=lambda *_a, **_k: retry_fake,
            notification_sender=None,
        )
        with app.db_session() as conn:
            count = conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0]
            statuses = conn.execute("SELECT status, marked_seen FROM infonalia_email_imports ORDER BY id").fetchall()
            resolved = conn.execute(
                "SELECT status FROM infonalia_email_import_incidents WHERE dedupe_key = ?",
                ("seen:<seen-retry@example.test>",),
            ).fetchone()

    assert first["committed_but_unseen"] == 1
    assert committed["status"] == "committed_but_unseen"
    assert committed["committed"] == 1 and committed["marked_seen"] == 0
    assert open_incident["status"] == "open"
    assert second["duplicates"] == 1
    assert retry_fake.messages[b"1"]["seen"] is True
    assert count == 1
    assert all(row["marked_seen"] == 1 for row in statuses)
    assert resolved["status"] == "resolved"


def test_transaction_failure_rolls_back_all_business_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    text = block_text() + block_text(ref="2026103763", expediente="CONTR 2026 0000264400")
    raw = strict_raw(plain=text, html_body=html_from_text(text), message_id="<rollback@example.test>")
    parsed = parse_infonalia_email(raw, strict=True)
    original = app.insert_payload
    calls = 0

    def fail_second(conn, payload, dia_id=None):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("fallo SQLite simulado")
        return original(conn, payload, dia_id)

    monkeypatch.setattr(app, "find_pdftotext", lambda: None)
    monkeypatch.setattr(app, "insert_payload", fail_second)
    with temporary_app_database(app):
        with pytest.raises(sqlite3.OperationalError, match="simulado"):
            import_parsed_email(parsed, raw_bytes=raw, notify=False)
        with app.db_session() as conn:
            assert conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0] == 0


def test_existing_same_key_with_material_difference_is_conflict_not_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    raw = strict_raw(plain=block_text(), html_body=html_from_text(block_text()), message_id="<db-conflict@example.test>")
    parsed = parse_infonalia_email(raw, strict=True)
    monkeypatch.setattr(app, "find_pdftotext", lambda: None)

    with temporary_app_database(app):
        with app.db_session() as conn:
            day_id = app.get_or_create_dia(conn, "2026-07-20")
            app.insert_payload(
                conn,
                {
                    "fecha_infonalia": "2026-07-20",
                    "expediente": "CONTR 2026 0000264070",
                    "organismo": "AGENCIA DE SEGURIDAD Y GESTIÓN INTEGRAL DE EMERGENCIAS DE ANDALUCÍA (ASEMA)",
                    "objeto": "Objeto editado manualmente y materialmente distinto",
                    "estado": "Importada",
                },
                day_id,
            )
        result = import_parsed_email(parsed, raw_bytes=raw, notify=False)
        with app.db_session() as conn:
            row = conn.execute("SELECT objeto FROM licitaciones").fetchone()
            block_audit = conn.execute("SELECT result_status FROM infonalia_email_import_blocks").fetchone()

    assert result["status"] == "quarantined"
    assert result["conflicts"] == 1
    assert row["objeto"] == "Objeto editado manualmente y materialmente distinto"
    assert block_audit["result_status"] == "conflict"


def test_mailbox_transaction_failure_stays_unseen_and_creates_incident(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    text = block_text() + block_text(ref="2026103763", expediente="CONTR 2026 0000264400")
    raw = strict_raw(plain=text, html_body=html_from_text(text), message_id="<rollback-mailbox@example.test>")
    fake = FakeIMAP({b"1": {"seen": False, "raw": raw}})
    original = app.insert_payload
    calls = 0

    def fail_second(conn, payload, dia_id=None):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("fallo transaccional simulado")
        return original(conn, payload, dia_id)

    monkeypatch.setattr(app, "find_pdftotext", lambda: None)
    monkeypatch.setattr(app, "insert_payload", fail_second)
    with temporary_app_database(app):
        result = process_mailbox_once(
            config=strict_config(),
            imap_factory=lambda *_a, **_k: fake,
            notification_sender=None,
        )
        with app.db_session() as conn:
            business_count = conn.execute("SELECT COUNT(*) FROM licitaciones").fetchone()[0]
            audit = conn.execute("SELECT status, committed FROM infonalia_email_imports").fetchone()
            incident = conn.execute("SELECT status FROM infonalia_email_import_incidents").fetchone()

    assert result["errors"] == 1
    assert fake.messages[b"1"]["seen"] is False
    assert business_count == 0
    assert audit["status"] == "quarantined" and audit["committed"] == 0
    assert incident["status"] == "open"


def test_smtp_failure_keeps_incident_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()
    raw = strict_raw(plain=block_text(), html_body="<html><body>Ref. Infonalia: 2026103762</body></html>")
    parsed = parse_infonalia_email(raw, strict=True)

    with temporary_app_database(app):
        result = import_parsed_email(
            parsed,
            raw_bytes=raw,
            notification_sender=lambda *_a: (_ for _ in ()).throw(RuntimeError("SMTP simulado")),
        )
        with app.db_session() as conn:
            incident = conn.execute("SELECT * FROM infonalia_email_import_incidents").fetchone()

    assert result["status"] == "quarantined"
    assert "SMTP simulado" in result["notification_error"]
    assert incident["status"] == "open"
    assert "SMTP simulado" in incident["alert_error"]


def test_manual_msg_strict_path_uses_same_reconciliation_core(monkeypatch: pytest.MonkeyPatch) -> None:
    app = load_app_module()

    class FakeMessage:
        date = "20/07/2026"
        body = block_text()
        htmlBody = html_from_text(block_text()).encode("utf-8")

        def __init__(self, _path: str) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setenv("LLANGON_INFONALIA_STRICT_IMPORT_ENABLED", "1")
    monkeypatch.setitem(sys.modules, "extract_msg", type("FakeExtractMsg", (), {"Message": FakeMessage}))
    with temporary_app_database(app):
        result = app.import_msg_content(b"fixture msg", enrich_pdf=False, input_name="fixture.msg")
        with app.db_session() as conn:
            row = conn.execute("SELECT expediente FROM licitaciones").fetchone()

    assert result["importadas"] == 1
    assert row["expediente"] == "CONTR 2026 0000264070"
