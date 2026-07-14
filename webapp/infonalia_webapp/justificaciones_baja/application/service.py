"""Use cases for one-lot low-bid justifications.

The service orchestrates the pure Phase 1 engine and Phase 2B document layer.
It deliberately contains no economic formula and has no HTTP dependency.
"""

from __future__ import annotations

import hashlib
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from ..calculations import calculate_justification, economic_payload
from ..cost_generation import (
    generate_initial_costs,
    recalculate_products,
    remove_manual_cost,
    set_manual_cost,
    set_product_lock,
)
from ..documents import generate_excel, generate_word
from ..documents.payload import (
    IdentificationInput,
    NarrativeInput,
    RouteImageReference,
    TransportDocumentInput,
    build_document_payload,
)
from ..documents.validators import InvalidRouteImageError, inspect_route_image
from ..domain import CostActionResult, DomainValueError
from ..imports import parse_decimal
from ..snapshot import SnapshotMetadata, create_snapshot, load_snapshot
from ..persistence import (
    JustificationConflictError,
    JustificationNotFoundError,
    JustificationRepository,
)
from .dto import (
    calculate_draft,
    domain_from_draft,
    initial_draft,
    merge_domain_into_draft,
    normalise_draft,
)
from .errors import (
    JustificationConflictApplicationError,
    JustificationNotFoundApplicationError,
    JustificationStorageError,
    JustificationValidationError,
)


Clock = Callable[[], datetime]
ALLOWED_STATES = frozenset({"borrador", "enviado_cliente", "final"})


class JustificationApplicationService:
    def __init__(
        self,
        repository: JustificationRepository,
        *,
        clock: Clock | None = None,
        random_source: Any | None = None,
        temporary_root: str | Path | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.random_source = random_source or secrets.SystemRandom()
        self.temporary_root = Path(temporary_root or Path.cwd() / "tmp" / "justificaciones_baja_runtime").resolve(strict=False)

    def create(
        self,
        *,
        licitacion: Mapping[str, Any],
        cliente: Mapping[str, Any],
        lote_numero: str,
        lote_nombre: str = "",
        declared_offer: object = "0",
        proposals: Mapping[str, Any] | None = None,
        draft: Mapping[str, Any] | None = None,
        user_id: str,
    ) -> dict[str, Any]:
        initial = initial_draft(
            licitacion=licitacion,
            cliente=cliente,
            lote_numero=lote_numero,
            lote_nombre=lote_nombre,
            declared_offer=declared_offer,
            proposals=proposals,
        )
        timestamp = self._timestamp()
        try:
            if draft is None:
                record = self.repository.create(
                    licitacion_id=int(licitacion["id"]),
                    cliente_id=int(cliente["id"]),
                    expediente=initial["identification"]["expediente"],
                    lote_numero=initial["identification"]["lot_number"],
                    lote_nombre=initial["identification"]["lot_name"],
                    draft=initial,
                    user_id=user_id,
                    timestamp=timestamp,
                )
            else:
                value = normalise_draft(draft)
                financial = _persistence_financials(value)
                record = self.repository.create_with_draft(
                    licitacion_id=int(licitacion["id"]),
                    initial_cliente_id=int(cliente["id"]),
                    expediente=initial["identification"]["expediente"],
                    lote_numero=initial["identification"]["lot_number"],
                    lote_nombre=initial["identification"]["lot_name"],
                    initial_draft=initial,
                    draft=value,
                    cliente_id=_draft_cliente_id(value),
                    **financial,
                    user_id=user_id,
                    timestamp=timestamp,
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise JustificationValidationError(str(exc) or "No se pudo crear la justificación.") from exc
        return self._detail(record)

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list(**filters)

    def get(self, justification_id: int) -> dict[str, Any]:
        try:
            return self._detail(self.repository.get(justification_id))
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc

    def preview(self, draft: Mapping[str, Any]) -> dict[str, Any]:
        value = normalise_draft(draft)
        return {"draft": value, "calculation": calculate_draft(value)}

    def save(
        self,
        justification_id: int,
        *,
        draft: Mapping[str, Any],
        expected_revision: int,
        user_id: str,
        event_type: str = "saved",
        event_message: str = "Borrador guardado.",
        event_metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            value = normalise_draft(draft)
        except (DomainValueError, KeyError, TypeError, ValueError) as exc:
            raise JustificationValidationError(str(exc)) from exc
        return self._persist_draft(
            justification_id,
            value=value,
            expected_revision=expected_revision,
            user_id=user_id,
            event_type=event_type,
            event_message=event_message,
            event_metadata=event_metadata,
        )

    def generate_costs(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        user_id: str,
    ) -> dict[str, Any]:
        return self._cost_action(
            justification_id,
            expected_revision=expected_revision,
            user_id=user_id,
            action=lambda value: generate_initial_costs(value, self.random_source),
            event_type="costs_generated",
            event_message="Costes estimados generados explícitamente.",
        )

    def recalculate_costs(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        line_ids: list[str] | tuple[str, ...] | None,
        user_id: str,
    ) -> dict[str, Any]:
        selected = None if line_ids is None else tuple(str(item) for item in line_ids)

        def action(value: Any) -> Any:
            ids = (
                tuple(product.line_id for product in value.products if not product.locked)
                if selected is None
                else selected
            )
            return recalculate_products(value, ids, self.random_source)

        return self._cost_action(
            justification_id,
            expected_revision=expected_revision,
            user_id=user_id,
            action=action,
            event_type="costs_recalculated",
            event_message="Costes estimados recalculados explícitamente.",
            metadata={"line_ids": list(selected) if selected is not None else "unlocked"},
        )

    def set_manual_cost(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        line_id: str,
        manual_unit_cost: object,
        user_id: str,
    ) -> dict[str, Any]:
        return self._cost_action(
            justification_id,
            expected_revision=expected_revision,
            user_id=user_id,
            action=lambda value: set_manual_cost(
                value,
                line_id,
                parse_decimal(manual_unit_cost, field="manual_unit_cost"),
            ),
            event_type="manual_cost_set",
            event_message="Coste unitario editado manualmente.",
            metadata={"line_id": line_id},
        )

    def remove_manual_cost(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        line_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        return self._cost_action(
            justification_id,
            expected_revision=expected_revision,
            user_id=user_id,
            action=lambda value: remove_manual_cost(value, line_id),
            event_type="manual_cost_removed",
            event_message="Se retiró la edición manual del coste.",
            metadata={"line_id": line_id},
        )

    def set_product_lock(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        line_id: str,
        locked: bool,
        user_id: str,
    ) -> dict[str, Any]:
        return self.set_product_locks(
            justification_id,
            expected_revision=expected_revision,
            line_ids=[line_id],
            locked=locked,
            user_id=user_id,
        )

    def set_product_locks(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        line_ids: list[str] | tuple[str, ...],
        locked: bool,
        user_id: str,
    ) -> dict[str, Any]:
        if not isinstance(locked, bool):
            raise JustificationValidationError("locked debe ser booleano.")
        selected = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in line_ids
                if item is not None and str(item).strip()
            )
        )
        if not selected:
            raise JustificationValidationError("line_ids debe contener al menos una línea.")

        def action(value: Any) -> CostActionResult:
            current = value
            warnings = ()
            for line_id in selected:
                result = set_product_lock(current, line_id, locked=locked)
                warnings += result.warnings
                if result.errors:
                    return CostActionResult(
                        justification=value,
                        errors=result.errors,
                        warnings=warnings,
                    )
                current = result.justification
            return CostActionResult(justification=current, warnings=warnings)

        return self._cost_action(
            justification_id,
            expected_revision=expected_revision,
            user_id=user_id,
            action=action,
            event_type="products_locked" if locked else "products_unlocked",
            event_message="Productos bloqueados." if locked else "Productos desbloqueados.",
            metadata={"line_ids": list(selected), "locked": locked},
            bulk_lock=(selected, locked),
        )

    def attach_route_image(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        filename: str,
        content: bytes,
        user_id: str,
    ) -> dict[str, Any]:
        if not isinstance(content, bytes) or not content:
            raise JustificationValidationError("La imagen de ruta está vacía.")
        self.temporary_root.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            raise JustificationValidationError("La imagen debe ser PNG o JPEG.")
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix="route_",
                suffix=suffix,
                dir=self.temporary_root,
                delete=False,
            ) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            reference = inspect_route_image(temporary, logical_name=Path(filename).name)
            with self.repository.atomic():
                record = self.repository.get(justification_id)
                asset = self.repository.put_route_image(
                    justification_id,
                    expected_revision=expected_revision,
                    original_name=reference.logical_name,
                    mime_type=reference.mime_type,
                    width_px=reference.width_px,
                    height_px=reference.height_px,
                    sha256=reference.sha256,
                    size_bytes=reference.size_bytes,
                    content=content,
                    user_id=user_id,
                    timestamp=self._timestamp(),
                )
                draft = normalise_draft(record["draft"])
                draft["route_image"] = {
                    "asset_id": asset["id"],
                    "logical_name": reference.logical_name,
                    "mime_type": reference.mime_type,
                    "width_px": reference.width_px,
                    "height_px": reference.height_px,
                    "sha256": reference.sha256,
                    "size_bytes": reference.size_bytes,
                }
                result = self.save(
                    justification_id,
                    draft=draft,
                    expected_revision=expected_revision,
                    user_id=user_id,
                    event_type="route_image_attached",
                    event_message="Imagen de ruta validada y adjuntada.",
                    event_metadata={"sha256": reference.sha256, "asset_id": asset["id"]},
                )
            return result
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc
        except JustificationConflictError as exc:
            raise JustificationConflictApplicationError(str(exc)) from exc
        except JustificationValidationError:
            raise
        except InvalidRouteImageError as exc:
            raise JustificationValidationError(str(exc)) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def freeze(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        user_id: str,
    ) -> dict[str, Any]:
        try:
            record = self.repository.get(justification_id)
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc
        draft = normalise_draft(record["draft"])
        if draft.get("route_image"):
            reference = draft["route_image"]
            asset = self.repository.get_route_image(
                justification_id, asset_id=reference["asset_id"]
            )
            if asset is None or (
                str(asset["sha256"]).upper() != reference["sha256"]
                or asset["mime_type"] != reference["mime_type"]
                or int(asset["width_px"]) != reference["width_px"]
                or int(asset["height_px"]) != reference["height_px"]
                or int(asset["size_bytes"]) != reference["size_bytes"]
            ):
                raise JustificationValidationError(
                    "La imagen de ruta no coincide con el asset validado de la justificación."
                )
        try:
            domain = domain_from_draft(draft)
        except (DomainValueError, ValueError, TypeError) as exc:
            raise JustificationValidationError(str(exc)) from exc
        calculation = calculate_justification(domain)
        if not calculation.is_valid:
            raise JustificationValidationError(
                "El borrador contiene errores que impiden congelar la versión.",
                issues=economic_payload(calculation)["errors"],
            )
        timestamp = self._timestamp()
        built = create_snapshot(
            domain,
            calculation,
            SnapshotMetadata(created_at=timestamp, created_by=user_id),
        )
        if not built.is_valid or built.snapshot is None:
            raise JustificationValidationError(
                "No se pudo construir el snapshot económico.",
                issues=[_issue_dict(item) for item in built.errors],
            )
        snapshot_json = built.snapshot.to_json()
        snapshot_sha256 = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest().upper()
        context = self._document_context(draft, generated_at=timestamp, generated_by=user_id)
        try:
            version = self.repository.freeze(
                justification_id,
                expected_revision=expected_revision,
                snapshot_json=snapshot_json,
                snapshot_sha256=snapshot_sha256,
                document_context=context,
                snapshot_schema_version=built.snapshot.schema_version,
                algorithm_version=built.snapshot.algorithm_version,
                user_id=user_id,
                timestamp=timestamp,
            )
        except JustificationConflictError as exc:
            raise JustificationConflictApplicationError(str(exc)) from exc
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc
        return {"version": version, "item": self.get(justification_id)}

    def update_state(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        state: str,
        user_id: str,
    ) -> dict[str, Any]:
        if state not in ALLOWED_STATES:
            raise JustificationValidationError("El estado indicado no es válido.")
        try:
            return self._detail(
                self.repository.update_state(
                    justification_id,
                    expected_revision=expected_revision,
                    state=state,
                    user_id=user_id,
                    timestamp=self._timestamp(),
                )
            )
        except JustificationConflictError as exc:
            raise JustificationConflictApplicationError(str(exc)) from exc
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc

    def generate_documents(
        self,
        justification_id: int,
        *,
        version_number: int,
        output_directory: str | Path,
        dropbox_base: str | Path,
        user_id: str,
    ) -> dict[str, Any]:
        """Generate Word and Excel from one immutable payload, then register both."""

        try:
            version = self.repository.get_version(
                justification_id, version_number=version_number
            )
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc
        loaded = load_snapshot(version["snapshot_json"])
        if not loaded.is_valid or loaded.snapshot is None:
            raise JustificationValidationError(
                "La versión congelada no puede reconstruirse de forma íntegra.",
                issues=[_issue_dict(item) for item in loaded.errors],
            )
        context = version["document_context"]
        image_reference, image_path = self._materialize_frozen_image(
            justification_id, context.get("route_image")
        )
        try:
            payload = build_document_payload(
                loaded.snapshot,
                IdentificationInput(**context["identification"]),
                NarrativeInput(
                    **{
                        **context["narrative"],
                        "arguments": tuple(context["narrative"].get("arguments", ())),
                        "pending_validation_fields": tuple(
                            context["narrative"].get("pending_validation_fields", ())
                        ),
                    }
                ),
                TransportDocumentInput(**context["transport_document"]),
                route_image=image_reference,
                generated_at=context["generated_at"],
                generated_by=context["generated_by"],
                draft=True,
            )
            output = Path(output_directory).resolve(strict=False)
            base = Path(dropbox_base).resolve(strict=True)
            try:
                output.relative_to(base)
            except ValueError as exc:
                raise JustificationStorageError("La salida queda fuera de la base Dropbox validada.") from exc
            if output.exists() and not output.is_dir():
                raise JustificationStorageError("La salida documental no es una carpeta.")
            documents = self.repository.list_documents(justification_id)
            same_version = [
                item for item in documents if int(item.get("version_id") or 0) == int(version["id"])
            ]
            first_generation_number = max(
                [int(item.get("generation_number") or 0) for item in same_version] or [0]
            ) + 1
            version_directory = output / f"Version_{version_number:03d}"
            for generation_number in range(first_generation_number, 10_000):
                word_result = None
                excel_result = None
                try:
                    word_result = generate_word(
                        payload,
                        version_directory,
                        route_image_path=image_path,
                        version=generation_number,
                    )
                    excel_result = generate_excel(
                        payload,
                        version_directory,
                        route_image_path=image_path,
                        version=generation_number,
                    )
                    if word_result.payload_sha256 != excel_result.payload_sha256:
                        raise JustificationValidationError("Word y Excel no proceden del mismo payload.")
                    timestamp = self._timestamp()
                    registered = []
                    with self.repository.atomic():
                        for kind, result in (("word", word_result), ("excel", excel_result)):
                            relative = result.path.resolve(strict=True).relative_to(base).as_posix()
                            registered.append(
                                self.repository.add_document(
                                    justification_id,
                                    version_id=int(version["id"]),
                                    document_type=kind,
                                    generation_number=generation_number,
                                    file_name=result.path.name,
                                    relative_path=relative,
                                    sha256=result.sha256,
                                    size_bytes=result.size_bytes,
                                    payload_sha256=result.payload_sha256,
                                    template_version=result.template_version,
                                    user_id=user_id,
                                    timestamp=timestamp,
                                )
                            )
                    return {
                        "version_number": version_number,
                        "generation_number": generation_number,
                        "snapshot_sha256": version["snapshot_sha256"],
                        "payload_sha256": payload.sha256,
                        "documents": registered,
                        "item": self.get(justification_id),
                    }
                except FileExistsError:
                    for result in (word_result, excel_result):
                        if result is not None:
                            result.path.unlink(missing_ok=True)
                    continue
                except Exception:
                    for result in (word_result, excel_result):
                        if result is not None:
                            result.path.unlink(missing_ok=True)
                    raise
            raise JustificationConflictApplicationError(
                "No se pudo reservar una generación documental libre. Reintenta la operación."
            )
        except JustificationConflictError as exc:
            raise JustificationConflictApplicationError(str(exc)) from exc
        finally:
            if image_path is not None:
                image_path.unlink(missing_ok=True)

    def _persist_draft(
        self,
        justification_id: int,
        *,
        value: Mapping[str, Any],
        expected_revision: int,
        user_id: str,
        event_type: str,
        event_message: str,
        event_metadata: Mapping[str, Any] | None,
        bulk_lock: tuple[tuple[str, ...], bool] | None = None,
    ) -> dict[str, Any]:
        financial = _persistence_financials(value)
        common = {
            "expected_revision": expected_revision,
            "draft": value,
            "cliente_id": _draft_cliente_id(value),
            "expediente": value["identification"]["expediente"],
            "lote_numero": value["identification"]["lot_number"],
            "lote_nombre": value["identification"]["lot_name"],
            **financial,
            "user_id": user_id,
            "timestamp": self._timestamp(),
        }
        try:
            if bulk_lock is None:
                record = self.repository.update_draft(
                    justification_id,
                    **common,
                    event_type=event_type,
                    event_message=event_message,
                    event_metadata=event_metadata,
                )
            else:
                line_ids, locked = bulk_lock
                record = self.repository.update_product_locks(
                    justification_id,
                    **common,
                    line_ids=line_ids,
                    locked=locked,
                    event_metadata=event_metadata,
                )
        except JustificationConflictError as exc:
            raise JustificationConflictApplicationError(str(exc)) from exc
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise JustificationValidationError(str(exc)) from exc
        return self._detail(record)

    def _cost_action(
        self,
        justification_id: int,
        *,
        expected_revision: int,
        user_id: str,
        action: Callable[[Any], Any],
        event_type: str,
        event_message: str,
        metadata: Mapping[str, Any] | None = None,
        bulk_lock: tuple[tuple[str, ...], bool] | None = None,
    ) -> dict[str, Any]:
        try:
            record = self.repository.get(justification_id)
            domain = domain_from_draft(record["draft"])
            result = action(domain)
        except JustificationNotFoundError as exc:
            raise JustificationNotFoundApplicationError(str(exc)) from exc
        except (DomainValueError, ValueError, TypeError) as exc:
            raise JustificationValidationError(str(exc)) from exc
        if not result.is_valid:
            raise JustificationValidationError(
                "La acción de costes no pudo aplicarse.",
                issues=[_issue_dict(item) for item in result.errors],
            )
        draft = merge_domain_into_draft(record["draft"], result.justification)
        event_metadata = {
            **dict(metadata or {}),
            "warnings": [_issue_dict(item) for item in result.warnings],
        }
        if bulk_lock is not None:
            return self._persist_draft(
                justification_id,
                value=normalise_draft(draft),
                expected_revision=expected_revision,
                user_id=user_id,
                event_type=event_type,
                event_message=event_message,
                event_metadata=event_metadata,
                bulk_lock=bulk_lock,
            )
        return self.save(
            justification_id,
            draft=draft,
            expected_revision=expected_revision,
            user_id=user_id,
            event_type=event_type,
            event_message=event_message,
            event_metadata=event_metadata,
        )

    def _detail(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(record)
        draft = result.get("draft")
        result["calculation"] = calculate_draft(draft) if isinstance(draft, Mapping) else None
        return result

    def _document_context(
        self,
        draft: Mapping[str, Any],
        *,
        generated_at: str,
        generated_by: str,
    ) -> dict[str, Any]:
        identification = dict(draft["identification"])
        client = draft["client"]
        identification.update(
            {
                "client": client["name"],
                "nif": client["nif"],
                "address": client["address"],
                "phone": client["phone"],
                "email": client["email"],
                "representative": client["representative"],
                "representative_dni": client["representative_dni"],
                "role": client["role"],
                "signatory": client["signatory"],
            }
        )
        return {
            "identification": identification,
            "narrative": dict(draft["narrative"]),
            "transport_document": dict(draft["transport_document"]),
            "route_image": dict(draft["route_image"]) if draft.get("route_image") else None,
            "accepted_warning_codes": list(draft.get("accepted_warning_codes", ())),
            "generated_at": generated_at,
            "generated_by": generated_by,
        }

    def _materialize_frozen_image(
        self, justification_id: int, raw_reference: object
    ) -> tuple[RouteImageReference | None, Path | None]:
        if not isinstance(raw_reference, Mapping):
            return None, None
        asset_id = raw_reference.get("asset_id")
        asset = self.repository.get_route_image(justification_id, asset_id=asset_id)
        if asset is None:
            raise JustificationValidationError("La imagen congelada ya no está disponible.")
        self.temporary_root.mkdir(parents=True, exist_ok=True)
        suffix = ".png" if asset["mime_type"] == "image/png" else ".jpg"
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix="route_frozen_", suffix=suffix, dir=self.temporary_root, delete=False
        ) as handle:
            handle.write(asset["content"])
            path = Path(handle.name)
        reference = inspect_route_image(path, logical_name=raw_reference["logical_name"])
        expected = (
            raw_reference["mime_type"],
            int(raw_reference["width_px"]),
            int(raw_reference["height_px"]),
            str(raw_reference["sha256"]).upper(),
            int(raw_reference["size_bytes"]),
        )
        actual = (
            reference.mime_type,
            reference.width_px,
            reference.height_px,
            reference.sha256.upper(),
            reference.size_bytes,
        )
        if actual != expected:
            path.unlink(missing_ok=True)
            raise JustificationValidationError("La imagen no coincide con la referencia congelada.")
        return reference, path

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _draft_cliente_id(draft: Mapping[str, Any]) -> int:
    client = draft.get("client")
    if not isinstance(client, Mapping):
        raise ValueError("El borrador no contiene una sección de cliente válida.")
    raw = client.get("client_id")
    if isinstance(raw, bool):
        raise ValueError("client.client_id debe ser un identificador válido.")
    try:
        cliente_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("client.client_id debe ser un identificador válido.") from exc
    if cliente_id <= 0 or str(raw).strip() != str(cliente_id):
        raise ValueError("client.client_id debe ser un identificador válido.")
    return cliente_id


def _persistence_financials(draft: Mapping[str, Any]) -> dict[str, str | None]:
    calculation = calculate_draft(draft)
    values = calculation.get("values") or {}
    raw = values.get("raw") or {}
    display = values.get("display") or {}
    return {
        "profit_raw": raw.get("profit"),
        "profit_display": display.get("profit"),
        "profit_percentage_raw": raw.get("profit_percentage"),
        "profit_percentage_display": display.get("profit_percentage"),
    }


def _issue_dict(issue: Any) -> dict[str, Any]:
    return {
        "code": issue.code,
        "severity": issue.severity.value,
        "message": issue.message,
        "field": issue.field,
        "line_id": issue.line_id,
        "metadata": issue.metadata_dict(),
    }
