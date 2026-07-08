from __future__ import annotations

import json
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from ..normalization import bool_text, clean_text
except ImportError:
    from normalization import bool_text, clean_text


TELEGRAM_ENABLED_ENV = "LLANGON_TELEGRAM_ENABLED"
TELEGRAM_BOT_TOKEN_ENV = "LLANGON_TELEGRAM_BOT_TOKEN"
TELEGRAM_GROUP_CHAT_ID_ENV = "LLANGON_TELEGRAM_GROUP_CHAT_ID"
DEFAULT_TELEGRAM_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class TelegramResult:
    ok: bool
    status: str
    message: str
    error_code: str = ""
    error_message: str = ""
    telegram_message_id: int | None = None
    provider_status: int | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": self.ok,
            "status": self.status,
            "message": self.message,
        }
        if self.error_code:
            payload["error_code"] = self.error_code
        if self.error_message:
            payload["error_message"] = self.error_message
        if self.telegram_message_id is not None:
            payload["telegram_message_id"] = self.telegram_message_id
        if self.provider_status is not None:
            payload["provider_status"] = self.provider_status
        return payload


def normalize_telegram_chat_id(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("-") and text[1:].isdigit():
        return text
    if text.isdigit():
        return text
    return ""


def telegram_enabled(env: Mapping[str, object] | None = None) -> bool:
    values = env or {}
    return bool_text(values.get(TELEGRAM_ENABLED_ENV, "0"))


def telegram_bot_token(env: Mapping[str, object] | None = None) -> str:
    values = env or {}
    return clean_text(values.get(TELEGRAM_BOT_TOKEN_ENV))


def telegram_group_chat_id(env: Mapping[str, object] | None = None) -> str:
    values = env or {}
    return normalize_telegram_chat_id(values.get(TELEGRAM_GROUP_CHAT_ID_ENV))


def telegram_public_status(env: Mapping[str, object] | None = None) -> dict[str, object]:
    values = env or {}
    enabled = telegram_enabled(values)
    token_configured = bool(telegram_bot_token(values))
    group_configured = bool(telegram_group_chat_id(values))
    if not enabled:
        status_label = "Telegram desactivado"
    elif not token_configured:
        status_label = "Falta el token del bot"
    elif not group_configured:
        status_label = "Falta el chat general"
    else:
        status_label = "Telegram listo"
    return {
        "enabled": enabled,
        "token_configured": token_configured,
        "group_configured": group_configured,
        "status_label": status_label,
    }


def mapping_value(values: object, key: str, default: object = "") -> object:
    if values is None:
        return default
    if isinstance(values, Mapping):
        return values.get(key, default)
    keys = getattr(values, "keys", None)
    if callable(keys):
        try:
            if key in keys():
                return values[key]  # type: ignore[index]
        except (KeyError, TypeError, IndexError):
            return default
    return default


def _redact_telegram_secrets(text: object, token: str = "", chat_id: str = "") -> str:
    safe_text = clean_text(text)
    for secret in {clean_text(token), clean_text(chat_id)}:
        if secret:
            safe_text = safe_text.replace(secret, "[protegido]")
    return safe_text


def _read_telegram_http_error(exc: HTTPError) -> dict[str, object]:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return {}
    if not body:
        return {}
    try:
        parsed = json.loads(body)
    except ValueError:
        return {"description": body}
    return parsed if isinstance(parsed, dict) else {"description": body}


def _telegram_rejection_message(
    *,
    status_code: int | None,
    description: object,
    token: str = "",
    chat_id: str = "",
) -> str:
    safe_description = _redact_telegram_secrets(description, token=token, chat_id=chat_id)
    lower_description = safe_description.lower()

    if "chat not found" in lower_description:
        return (
            "Telegram no encuentra el grupo configurado. Revisa que el bot esté añadido al grupo "
            "y que LLANGON_TELEGRAM_GROUP_CHAT_ID sea el ID correcto; en supergrupos normalmente "
            "empieza por -100."
        )
    if "upgraded to a supergroup" in lower_description or "migrate_to_chat_id" in lower_description:
        return (
            "El grupo de Telegram parece haberse migrado a supergrupo. Actualiza "
            "LLANGON_TELEGRAM_GROUP_CHAT_ID con el nuevo ID del grupo, normalmente empezando por -100."
        )
    if "bot was blocked" in lower_description:
        return "Telegram indica que el bot está bloqueado en ese chat. Desbloquéalo o vuelve a añadirlo."
    if "not enough rights" in lower_description or "bot is not a member" in lower_description:
        return "Telegram indica que el bot no tiene permisos suficientes o no pertenece al grupo."
    if "message text is empty" in lower_description:
        return "Telegram ha rechazado el aviso porque el mensaje está vacío."
    if safe_description:
        return f"Telegram devolvió HTTP {status_code}: {safe_description}" if status_code else safe_description
    return f"Telegram devolvió HTTP {status_code}." if status_code else "Telegram rechazó el mensaje."


def send_telegram_message(
    chat_id: str,
    text: str,
    *,
    env: Mapping[str, object] | None = None,
    timeout_seconds: float = DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
    sender: Callable[[str, dict[str, object], float], dict[str, object]] | None = None,
) -> TelegramResult:
    values = env or {}
    token = telegram_bot_token(values)
    if not token:
        return TelegramResult(
            ok=False,
            status="error",
            message="Telegram no configurado.",
            error_code="TELEGRAM_MISSING_TOKEN",
            error_message="Falta configurar el token del bot de Telegram.",
        )
    normalized_chat_id = normalize_telegram_chat_id(chat_id)
    if not normalized_chat_id:
        return TelegramResult(
            ok=False,
            status="error",
            message="Telegram no configurado.",
            error_code="TELEGRAM_INVALID_CHAT_ID",
            error_message="El chat de Telegram no es válido.",
        )

    transport = sender or _send_via_urllib
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": normalized_chat_id,
        "text": clean_text(text),
        "disable_web_page_preview": True,
    }
    try:
        response = transport(url, payload, timeout_seconds)
    except TimeoutError:
        return TelegramResult(
            ok=False,
            status="error",
            message="Error de Telegram/red.",
            error_code="TELEGRAM_TIMEOUT",
            error_message="Telegram no respondió dentro del tiempo configurado.",
        )
    except HTTPError as exc:
        error_payload = _read_telegram_http_error(exc)
        description = error_payload.get("description") or exc.reason
        return TelegramResult(
            ok=False,
            status="error",
            message="Error de Telegram/red.",
            error_code="TELEGRAM_HTTP_ERROR",
            error_message=_telegram_rejection_message(
                status_code=exc.code,
                description=description,
                token=token,
                chat_id=normalized_chat_id,
            ),
            provider_status=exc.code,
        )
    except (URLError, OSError) as exc:
        return TelegramResult(
            ok=False,
            status="error",
            message="Error de Telegram/red.",
            error_code="TELEGRAM_NETWORK_ERROR",
            error_message=_redact_telegram_secrets(exc, token=token, chat_id=normalized_chat_id),
        )
    except ValueError as exc:
        return TelegramResult(
            ok=False,
            status="error",
            message="Error de Telegram/red.",
            error_code="TELEGRAM_INVALID_RESPONSE",
            error_message=clean_text(exc),
        )

    if not bool(response.get("ok")):
        description = clean_text(response.get("description")) or "Telegram rechazó el mensaje."
        return TelegramResult(
            ok=False,
            status="error",
            message="Error de Telegram/red.",
            error_code="TELEGRAM_API_ERROR",
            error_message=_telegram_rejection_message(
                status_code=None,
                description=description,
                token=token,
                chat_id=normalized_chat_id,
            ),
        )

    result = response.get("result") or {}
    message_id = result.get("message_id")
    try:
        telegram_message_id = int(message_id) if message_id is not None else None
    except (TypeError, ValueError):
        telegram_message_id = None
    return TelegramResult(
        ok=True,
        status="ok",
        message="Enviado correctamente",
        telegram_message_id=telegram_message_id,
    )


def send_telegram_group_message(
    text: str,
    *,
    env: Mapping[str, object] | None = None,
    timeout_seconds: float = DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
    sender: Callable[[str, dict[str, object], float], dict[str, object]] | None = None,
) -> TelegramResult:
    values = env or {}
    if not telegram_enabled(values):
        return TelegramResult(
            ok=False,
            status="disabled",
            message="Telegram deshabilitado",
            error_code="TELEGRAM_DISABLED",
            error_message="Telegram deshabilitado.",
        )
    group_chat_id = telegram_group_chat_id(values)
    if not group_chat_id:
        return TelegramResult(
            ok=False,
            status="error",
            message="Telegram no configurado",
            error_code="TELEGRAM_MISSING_GROUP_CHAT_ID",
            error_message="Falta configurar el chat general de Telegram.",
        )
    return send_telegram_message(
        group_chat_id,
        text,
        env=values,
        timeout_seconds=timeout_seconds,
        sender=sender,
    )


def send_telegram_user_message(
    user: Mapping[str, object] | None,
    text: str,
    *,
    env: Mapping[str, object] | None = None,
    timeout_seconds: float = DEFAULT_TELEGRAM_TIMEOUT_SECONDS,
    sender: Callable[[str, dict[str, object], float], dict[str, object]] | None = None,
) -> TelegramResult:
    values = env or {}
    if not telegram_enabled(values):
        return TelegramResult(
            ok=False,
            status="disabled",
            message="Telegram deshabilitado",
            error_code="TELEGRAM_DISABLED",
            error_message="Telegram deshabilitado.",
        )
    if not user:
        return TelegramResult(
            ok=False,
            status="error",
            message="Telegram no configurado para este usuario",
            error_code="TELEGRAM_USER_NOT_FOUND",
            error_message="Usuario no encontrado.",
        )
    if not bool_text(mapping_value(user, "telegram_notifications_enabled")):
        return TelegramResult(
            ok=False,
            status="error",
            message="Telegram no configurado para este usuario",
            error_code="TELEGRAM_USER_DISABLED",
            error_message="Telegram desactivado para este usuario.",
        )
    chat_id = normalize_telegram_chat_id(mapping_value(user, "telegram_chat_id"))
    if not chat_id:
        return TelegramResult(
            ok=False,
            status="error",
            message="Telegram no configurado para este usuario",
            error_code="TELEGRAM_USER_MISSING_CHAT_ID",
            error_message="Telegram no configurado para este usuario.",
        )
    return send_telegram_message(
        chat_id,
        text,
        env=values,
        timeout_seconds=timeout_seconds,
        sender=sender,
    )


def _send_via_urllib(url: str, payload: dict[str, object], timeout_seconds: float) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except socket.timeout as exc:
        raise TimeoutError("Telegram timeout") from exc
    return json.loads(body)
