"""Contratos estáticos del frontend aislado de justificaciones de baja."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "static" / "justificaciones_baja.js"
CSS_PATH = ROOT / "static" / "justificaciones_baja.css"


def js_source() -> str:
    return JS_PATH.read_text(encoding="utf-8")


def css_source() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def test_frontend_is_kept_in_dedicated_assets() -> None:
    assert JS_PATH.is_file()
    assert CSS_PATH.is_file()
    assert "window.JustificacionesBaja =" not in (ROOT / "static" / "app.js").read_text(
        encoding="utf-8"
    )


def test_feature_is_wired_into_suite_navigation_and_licitation_detail() -> None:
    index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert '/static/justificaciones_baja.css' in index
    assert '/static/justificaciones_baja.js' in index
    assert 'data-nav-section="justificaciones-baja"' in index
    assert 'id="justificaciones-baja-section"' in index
    assert 'data-create-justificacion-baja=' in app
    assert 'data-open-justificaciones-baja=' in app
    assert 'window.JustificacionesBaja?.init' in app
    assert 'new CustomEvent("llangon:viewchange"' in app


def test_public_bridge_is_small_and_explicit() -> None:
    source = js_source()
    assert "global.JustificacionesBaja = Object.freeze" in source
    for member in ("init,", "showList: showListView", "showForLicitacion:", "openForLicitacion,", "openExisting,"):
        assert member in source
    assert "state.bridge.csrfHeaders" in source
    assert "state.bridge.navigate" in source


def test_api_map_matches_the_private_server_contract() -> None:
    source = js_source()
    required_fragments = (
        'const DEFAULT_API_BASE = "/api/justificaciones-baja"',
        "/costes/generar",
        "/costes/recalcular",
        "/costes/manual",
        "/costes/retirar-manual",
        "/productos/bloqueo",
        "/imagen-ruta",
        "/congelar",
        "/estado",
        "/preview",
        "/documentos",
        "/importar-xlsx/preview",
        "/pegar/preview",
        "/download",
    )
    for fragment in required_fragments:
        assert fragment in source


def test_private_mutations_use_csrf_and_same_origin_session() -> None:
    source = js_source()
    assert '"X-CSRF-Token"' in source
    assert 'credentials: "same-origin"' in source
    assert 'new Set(["GET", "HEAD", "OPTIONS"])' in source
    assert "Object.assign(headers, csrfHeaders())" in source
    assert 'global.location.href = "/login"' in source


def test_concurrency_conflict_and_unsaved_changes_are_visible() -> None:
    source = js_source()
    assert "class ConflictError" in source
    assert "response.status === 409" in source
    assert "data-jb-conflict" in source
    assert "data-jb-reload-conflict" in source
    assert 'global.addEventListener("beforeunload"' in source
    assert "state.current.revision" in source


def test_editor_contains_all_required_workflow_sections() -> None:
    source = js_source()
    for step in (
        "Identificación y cliente",
        "Contrato y periodicidad",
        "Transporte",
        "Productos",
        "Generación y ajuste de costes",
        "Narrativa e imagen",
        "Versiones y documentos",
    ):
        assert step in source
    assert "Resultado económico" in source


def test_transport_and_observatory_inputs_are_editable() -> None:
    source = js_source()
    fields = (
        "operational_weeks",
        "weekly_deliveries",
        "circular_kilometres",
        "effective_decimal_hours",
        "route_duration_text",
        "kilometre_rate",
        "hourly_rate",
        "contract_stops",
        "shared_orders",
        "vehicle_type",
        "observatory_date",
        "observatory_url",
        "general_expense_base",
        "general_expense_percentage",
        "indirect_costs",
    )
    for field in fields:
        assert f'name="{field}"' in source


def test_client_selection_copies_an_editable_snapshot() -> None:
    source = js_source()
    assert "async function loadClientSnapshot" in source
    assert "client_snapshot" in source
    for field in (
        "cliente_razon_social",
        "cliente_nif",
        "cliente_domicilio",
        "cliente_email",
        "representante_nombre",
        "representante_nif",
        "representante_cargo",
    ):
        assert field in source


def test_saved_draft_matches_the_closed_application_dto() -> None:
    source = js_source()
    for key in (
        "schema_version",
        "identification",
        "lot_number",
        "lot_name",
        "client_id",
        "transport_document",
        "observatory_date",
        "observatory_url",
        "accepted_warning_codes",
        "estimated_draft_notice",
        "pending_validation_fields",
    ):
        assert key in source
    assert "arguments: argumentsText ? argumentsText.split" in source


def test_first_save_is_one_atomic_post_with_the_complete_draft() -> None:
    source = js_source()
    block = re.search(
        r"async function saveCurrent\(.*?\n  }\n\n  function scheduleLivePreview",
        source,
        re.DOTALL,
    ).group(0)
    create_branch = re.search(r"else \{(.*?)\n      \}", block, re.DOTALL).group(1)
    assert create_branch.count('method: "POST"') == 1
    assert 'method: "PATCH"' not in create_branch
    assert "createdItem.revision" not in block
    assert "json: payload" in create_branch
    assert "draft," in re.search(
        r"function savePayload\(\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)


def test_products_support_manual_entry_import_and_stable_line_ids() -> None:
    source = js_source()
    assert "data-jb-add-product" in source
    assert "data-jb-open-xlsx" in source
    assert "data-jb-open-paste" in source
    assert "crypto?.randomUUID" in source
    assert "line_id" in source
    assert "data-jb-duplicate-product" in source
    assert "data-jb-delete-product" in source
    assert "data-jb-move-product" in source


def test_import_preview_supports_mapping_and_does_not_set_multipart_content_type() -> None:
    source = js_source()
    assert "new FormData()" in source
    assert 'formData.append("mapping", JSON.stringify(importMapping()))' in source
    assert 'formData.append("sheet_name", sheet)' in source
    assert "data-jb-import-start-row" in source
    assert 'data-jb-map="name"' in source
    assert 'data-jb-map="offered_amount"' in source
    multipart_call = re.search(
        r"request\(apiPaths\(\)\.xlsxPreview\(\),\s*\{ method: \"POST\", body: formData \}\)",
        source,
    )
    assert multipart_call


def test_cost_actions_are_explicit_and_product_selection_is_supported() -> None:
    source = js_source()
    for action in (
        "data-jb-generate-costs",
        "data-jb-recalculate-selected",
        "data-jb-recalculate-unlocked",
        "data-jb-lock-selected",
        "data-jb-unlock-selected",
        "data-jb-apply-manual",
        "data-jb-remove-manual",
    ):
        assert action in source
    assert "selectedLineIds: new Set()" in source
    assert "revision: state.current.revision" in source
    assert 'typeof pathBuilder === "function" ? pathBuilder(state.current.id)' in source
    assert "(id) => apiPaths().generateCosts(id)" in source
    assert "line_ids: lineIds, locked" in source
    assert "for (const lineId of lineIds)" not in source
    assert "{ state: status }" in source


def test_client_snapshot_keeps_full_address_and_place_and_is_immutable_after_create() -> None:
    source = js_source()
    assert "function joinedAddress(client)" in source
    for field in ("domicilio_fiscal", "codigo_postal", "municipio", "provincia"):
        assert f"client.{field}" in source
    assert "cliente_domicilio: joinedAddress(client)" in source
    assert "lugar: client.municipio" in source
    assert "client.disabled = !canEdit || Boolean(state.current?.id)" in source
    assert "draft.client?.client_id" in source
    assert "state.current = normalizeItem(payload);\n    state.permissions = payload.permissions || state.permissions;" in source
    assert "if (conflict) conflict.hidden = true;\n    fillEditorFields();" in source


def test_required_numeric_fields_are_validated_before_requests() -> None:
    source = js_source()
    assert "const REQUIRED_NUMERIC_FIELDS" in source
    assert "function numericTextIsValid" in source
    assert "function validateRequestFields" in source
    assert "Completa con números válidos" in source
    assert "validateRequestFields({ focus: true, announce: true })" in source
    assert "validateRequestFields({ focus: false" in source
    assert 'aria-invalid="true"' in source


def test_browser_does_not_implement_the_economic_engine() -> None:
    source = js_source()
    assert "Math.random" not in source
    assert "eval(" not in source
    assert "new Function(" not in source
    assert not re.search(r"declared_lot_offer\s*[-+*/]", source)
    assert not re.search(r"profit\s*=", source)
    assert not re.search(r"allocated_transport\s*=", source)
    assert "Calculado por el backend" in source


def test_cost_range_changes_do_not_call_generation_implicitly() -> None:
    source = js_source()
    generate_function = source.index("async function generateCosts()")
    generate_handler = source.index('target.closest("[data-jb-generate-costs]")')
    assert generate_function < generate_handler
    assert 'name="minimum_percentage"' in source
    assert 'name="maximum_percentage"' in source
    assert "data-live-economic" not in re.search(
        r'<label>Horquilla mínima.*?</label>\s*<label>Horquilla máxima.*?</label>',
        source,
        re.DOTALL,
    ).group(0)


def test_backend_values_render_summary_and_product_results() -> None:
    source = js_source()
    assert "state.current?.calculation?.values?.product_lines" in source
    assert "state.current?.calculation?.values || null" in source
    for key in (
        "prorated_product_cost",
        "gross_margin",
        "allocated_transport",
        "general_expenses",
        "total_cost",
        "profit_percentage",
        "visual_product_residual",
    ):
        assert key in source


def test_live_economic_preview_is_debounced_and_not_persisted() -> None:
    source = js_source()
    assert "function scheduleLivePreview()" in source
    assert "global.clearTimeout(state.liveSaveTimer)" in source
    assert "global.setTimeout(async () =>" in source
    assert "request(apiPaths().preview()" in source
    assert 'json: { draft: collectDraft() }' in source
    block = re.search(
        r"function scheduleLivePreview\(\).*?\n  }\n\n  function applyServerItem",
        source,
        re.DOTALL,
    ).group(0)
    assert "saveCurrent" not in block
    assert "setDirty(false)" not in block


def test_old_previews_cannot_repaint_over_edits_or_mutations() -> None:
    source = js_source()
    invalidation = re.search(
        r"function invalidateLivePreview\(\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert "global.clearTimeout(state.liveSaveTimer)" in invalidation
    assert "state.requestSerial += 1" in invalidation

    input_handler = re.search(
        r"function handleInput\(event\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert input_handler.index("invalidateLivePreview()") < input_handler.index(
        "scheduleLivePreview()"
    )

    preview = re.search(
        r"function scheduleLivePreview\(\).*?\n  }\n\n  function captureProductFocus",
        source,
        re.DOTALL,
    ).group(0)
    assert preview.index("const serial = state.requestSerial") < preview.index(
        "global.setTimeout(async () =>"
    )
    assert preview.count("serial !== state.requestSerial") == 2

    apply_server = re.search(
        r"function applyServerItem\(payload\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert apply_server.index("invalidateLivePreview()") < apply_server.index(
        "state.current = normalizeItem(payload)"
    )

    action = re.search(
        r"async function performAction\(.*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert action.index("setBusy(true, progress)") < action.index(
        "await ensureSaved({ withinMutation: true })"
    )
    assert "field.disabled = !canEdit || state.busy" in source


def test_import_preview_is_invalidated_when_any_source_input_changes() -> None:
    source = js_source()
    assert "importPreviewSerial: 0" in source
    assert "importPreviewSignature" in source
    assert "importPreviewPending: false" in source
    assert "function importInputSignature()" in source
    for input_fragment in (
        "file.name, file.size, file.lastModified, file.type",
        "startRow:",
        "sheet:",
        "mapping: importMapping()",
        "text:",
    ):
        assert input_fragment in source
    invalidation = re.search(
        r"function invalidateImportPreview\(.*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert "state.importPreviewSerial += 1" in invalidation
    assert "state.importPreview = null" in invalidation
    assert "state.importPreviewPending = false" in invalidation
    assert "confirm.disabled = true" in invalidation
    assert "target.innerHTML = \"\"" in invalidation
    assert source.count(
        'event.target.closest("[data-jb-import-dialog]")'
    ) >= 2
    assert "signature !== importInputSignature()" in source
    assert (
        "state.importPreviewSignature !== importInputSignature()" in source
    )


def test_client_snapshot_load_is_cancelled_ordered_and_blocks_save() -> None:
    source = js_source()
    assert "clientLoadSerial: 0" in source
    assert "clientLoadController: null" in source
    assert "clientLoading: false" in source
    client_load = re.search(
        r"async function loadClientSnapshot\(clientId\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert "state.clientLoadController?.abort()" in client_load
    assert "const serial = ++state.clientLoadSerial" in client_load
    assert "const controller = new AbortController()" in client_load
    assert "{ signal: controller.signal }" in client_load
    assert "serial !== state.clientLoadSerial" in client_load
    assert "String(selectedClient) !== String(clientId)" in client_load
    assert "state.clientLoading = true" in client_load
    assert "state.clientLoading = false" in client_load
    assert "if (state.clientLoading)" in source
    assert '["[data-jb-save]", canEdit && clientReady]' in source


def test_route_file_is_captured_before_a_save_can_repaint_the_form() -> None:
    source = js_source()
    upload = re.search(
        r"async function uploadRouteImage\(\).*?\n  }\n\n  async function attachExistingRouteImage",
        source,
        re.DOTALL,
    ).group(0)
    assert upload.index('const file = input.files?.[0]') < upload.index(
        "await ensureSaved({ withinMutation: true })"
    )
    assert upload.index("setBusy(true") < upload.index(
        "await ensureSaved({ withinMutation: true })"
    )
    assert upload.index('formData.append("image", file)') > upload.index(
        "await ensureSaved({ withinMutation: true })"
    )


def test_failed_implicit_save_always_explains_the_error_before_an_action() -> None:
    source = js_source()
    save = re.search(
        r"async function saveCurrent\(.*?\n  }\n\n  function scheduleLivePreview",
        source,
        re.DOTALL,
    ).group(0)
    assert 'validateRequestFields({ focus: true, announce: true })' in save
    assert 'else setResult("editor", error.message, "error")' in save
    assert 'if (!silent) setResult("editor", error.message' not in save
    assert "clientSnapshotMatchesSelection()" in save


def test_failed_client_load_cannot_save_the_previous_client_snapshot() -> None:
    source = js_source()
    client_load = re.search(
        r"async function loadClientSnapshot\(clientId\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert client_load.index('state.clientSnapshotValid = false') < client_load.index(
        'await request(apiPaths().client(clientId)'
    )
    assert client_load.index("clearClientSnapshotFields()") < client_load.index(
        'await request(apiPaths().client(clientId)'
    )
    assert 'state.clientSnapshotClientId = String(clientId)' in client_load
    assert 'state.clientSnapshotValid = true' in client_load
    permissions = re.search(
        r"function applyPermissions\(\).*?\n  }\n\n  function updateSelectionCount",
        source,
        re.DOTALL,
    ).group(0)
    assert "clientSnapshotMatchesSelection() && !state.clientLoading" in permissions
    assert '["[data-jb-save]", canEdit && clientReady]' in permissions


def test_stale_navigation_responses_cannot_replace_the_current_view() -> None:
    source = js_source()
    assert "navigationSerial: 0" in source
    assert "navigationController: null" in source
    for function_name in ("loadList", "openForLicitacion", "openExisting"):
        block = re.search(
            rf"async function {function_name}\(.*?\n  }}",
            source,
            re.DOTALL,
        ).group(0)
        assert "beginNavigationLoad()" in block
        assert "navigationLoadIsCurrent(serial, controller)" in block
        assert "signal: controller.signal" in block
        assert 'error?.name === "AbortError"' in block
    show_list = re.search(
        r"function showListView\(.*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert "cancelNavigationLoad()" in show_list


def test_list_navigation_confirms_and_clears_an_unsaved_editor() -> None:
    source = js_source()
    show_list = re.search(
        r"function showListView\(.*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert show_list.index("confirmDiscardForNavigation") < show_list.index(
        "invalidateLivePreview()"
    )
    for statement in (
        "setDirty(false)",
        "state.current = null",
        "state.conflict = false",
        "state.selectedLineIds.clear()",
    ):
        assert statement in show_list
    back_handler = re.search(
        r'if \(target\.closest\("\[data-jb-back-list\]"\)\).*?\n    }',
        source,
        re.DOTALL,
    ).group(0)
    assert "global.confirm" not in back_handler
    assert "showListView()" in back_handler

    confirmation = re.search(
        r"function confirmDiscardForNavigation\(message\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert "if (!global.confirm(message))" in confirmation
    assert "resumeDirtyEditor()" in confirmation
    assert "setDirty(false)" in confirmation


def test_module_navigation_resumes_a_dirty_editor_from_another_section() -> None:
    source = js_source()
    resume = re.search(
        r"function resumeDirtyEditor\(\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert "navigateToFeature(" in resume
    assert 'querySelector("[data-jb-list-view]").hidden = true' in resume
    assert 'querySelector("[data-jb-editor-view]").hidden = false' in resume
    navigation = re.search(
        r"const nav = event\.target\.closest\(.*?\n      }",
        source,
        re.DOTALL,
    ).group(0)
    assert "if (state.dirty && state.current) resumeDirtyEditor()" in navigation
    assert "else showListView()" in navigation


def test_change_event_preserves_the_live_backend_preview() -> None:
    source = js_source()
    change = re.search(
        r"async function handleChange\(event\).*?\n  }",
        source,
        re.DOTALL,
    ).group(0)
    assert 'event.target.matches("[data-live-economic], [data-product-field]")' in change
    assert "scheduleLivePreview()" in change


def test_calculation_errors_remain_visible_when_values_are_null() -> None:
    source = js_source()
    no_values = re.search(
        r"if \(!values\) \{(.*?)\n    \}",
        source,
        re.DOTALL,
    ).group(1)
    assert "data-jb-issues" in no_values
    assert "response.calculation?.errors?.length" in source
    assert "La previsualización contiene errores" in source


def test_route_image_is_optional_and_uploaded_safely() -> None:
    source = js_source()
    assert 'accept="image/png,image/jpeg"' in source
    assert 'formData.append("image", file)' in source
    assert 'formData.append("revision", String(state.current.revision))' in source
    assert "data-jb-route-relative-path" in source
    assert "data-jb-attach-existing-route-image" in source
    assert "async function attachExistingRouteImage" in source
    assert "relative_path: relativePath" in source
    assert "Su ausencia genera una advertencia, no bloquea el cálculo." in source


def test_versions_documents_status_and_history_are_present() -> None:
    source = js_source()
    assert "data-jb-freeze" in source
    assert "data-jb-generate-documents" in source
    assert "Word y Excel generados desde el mismo snapshot" in source
    assert "data-jb-change-status" in source
    assert "Enviado al cliente" in source
    assert "state.current?.history" in source
    assert "snapshot_sha256" in source


def test_document_download_uses_only_the_document_identifier() -> None:
    source = js_source()
    assert "documentDownload: (documentId)" in source
    assert "encodeURIComponent(documentId)" in source
    assert "relative_path" not in re.search(
        r"function renderVersions\(\).*?function updateEditorMeta",
        source,
        re.DOTALL,
    ).group(0)
    assert "file://" not in source


def test_permissions_disable_effectful_controls() -> None:
    source = js_source()
    assert "function applyPermissions()" in source
    permission_block = re.search(
        r"function applyPermissions\(\).*?\n  }\n\n  function updateSelectionCount",
        source,
        re.DOTALL,
    ).group(0)
    for permission in (
        "can_edit",
        "can_generate_costs",
        "can_freeze",
        "can_change_status",
        "can_generate_documents",
    ):
        assert permission in source
    for selector in (
        "data-jb-add-product",
        "data-jb-open-xlsx",
        "data-jb-open-paste",
        "data-jb-confirm-import",
        "data-jb-apply-manual",
        "data-jb-toggle-lock",
        "data-jb-lock-selected",
        "data-jb-move-product",
        "data-jb-duplicate-product",
        "data-jb-delete-product",
        "data-jb-attach-existing-route-image",
    ):
        assert f'["[{selector}]"' in permission_block
    assert "updateSelectionCount();\n    applyPermissions();" in source
    assert "field.disabled = !canEdit" in source


def test_client_does_not_send_ignored_query_or_action_fields() -> None:
    source = js_source()
    assert 'params.set("q"' not in source
    assert "minimum_percentage: minimum" not in source
    assert 'scope: "unlocked"' not in source
    assert "{ line_ids: selectedOnly ? [...state.selectedLineIds] : null }" in source


def test_css_is_scoped_and_has_desktop_and_mobile_layouts() -> None:
    styles = css_source()
    assert "#justificaciones-baja-section" in styles
    assert ".jb-editor-layout" in styles
    assert "grid-template-columns: minmax(0, 1fr) minmax(270px, 330px);" in styles
    assert ".jb-summary" in styles
    assert "position: sticky;" in styles
    assert "@media (max-width: 860px)" in styles
    assert "@media (max-width: 760px)" in styles
    assert "@media (max-width: 520px)" in styles
    assert "overflow: auto;" in styles


def test_css_provides_clear_warning_conflict_and_negative_states() -> None:
    styles = css_source()
    for selector in (
        ".jb-unsaved",
        ".jb-conflict",
        ".jb-negative",
        ".jb-issue-error",
        ".jb-issue-warning",
        ".jb-status-borrador",
        ".jb-status-enviado_cliente",
        ".jb-status-final",
    ):
        assert selector in styles
