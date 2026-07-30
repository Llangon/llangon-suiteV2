"""Sesión, autenticación y navegación JSF específicas de PLACE."""

from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from ..common.question_models import normalized_key
from .challenge import requiere_interaccion_place
from .errors import (
    PlaceAccessChallengeError,
    PlaceAuthenticationError,
    PlaceSessionError,
    PlaceStructureError,
)

LOGIN_URL = "https://contrataciondelestado.es/wps/portal/plataforma/empresas"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
TIMEOUT_SECONDS = 60
SUBMIT_FORM_RE = re.compile(r'''submitForm\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]''')


def soup_from_response(response: requests.Response) -> BeautifulSoup:
    return BeautifulSoup(response.content, "html.parser")


def asegurar_sin_reto_acceso(response: requests.Response, *, code: str) -> None:
    """Evita diagnosticar un WAF como un cambio del formulario de PLACE."""

    content = getattr(response, "content", None)
    if content is None:
        content = getattr(response, "text", "")
    if requiere_interaccion_place(content):
        raise PlaceAccessChallengeError(
            f"{code}: PLACE exige JavaScript antes de permitir la consulta."
        )


def build_form_payload(form: Tag) -> dict[str, object]:
    payload: dict[str, object] = {}
    for control in form.find_all(["input", "textarea", "select"]):
        name = control.get("name")
        if not name or control.has_attr("disabled"):
            continue
        if control.name == "input":
            field_type = str(control.get("type") or "text").lower()
            if field_type in {"button", "submit", "reset", "image", "file"}:
                continue
            if field_type in {"checkbox", "radio"} and not control.has_attr("checked"):
                continue
            payload[str(name)] = str(control.get("value") or "")
            continue
        if control.name == "textarea":
            payload[str(name)] = control.get_text()
            continue
        selected = control.find_all("option", selected=True)
        if not selected:
            first_option = control.find("option")
            selected = [first_option] if first_option else []
        values = [str(option.get("value") or "") for option in selected]
        payload[str(name)] = values if control.has_attr("multiple") else (values[0] if values else "")
    return payload


def submit_target(link: Tag) -> tuple[str, str]:
    match = SUBMIT_FORM_RE.search(str(link.get("onclick") or ""))
    if not match:
        raise PlaceStructureError("PLACE no expone el formulario esperado para esta acción.")
    return match.group(1), match.group(2)


def post_jsf_link(
    session: requests.Session,
    soup: BeautifulSoup,
    current_url: str,
    link: Tag,
) -> requests.Response:
    form_id, source_id = submit_target(link)
    form = soup.find("form", id=form_id)
    if not isinstance(form, Tag):
        raise PlaceStructureError("No se encontró el formulario de PLACE asociado a la acción.")
    payload = build_form_payload(form)
    payload[f"{form_id}:_idcl"] = source_id
    action_url = urljoin(current_url, str(form.get("action") or current_url))
    try:
        response = session.post(
            action_url,
            data=payload,
            timeout=TIMEOUT_SECONDS,
            headers={"Referer": current_url},
        )
    except requests.RequestException as exc:
        raise PlaceSessionError("La sesión de PLACE falló al navegar por la ficha.") from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        asegurar_sin_reto_acceso(response, code="PLACE_ACCESS_CHALLENGE")
        raise PlaceSessionError("La sesión de PLACE falló al navegar por la ficha.") from exc
    asegurar_sin_reto_acceso(response, code="PLACE_ACCESS_CHALLENGE")
    return response


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def login(session: requests.Session, username: str, password: str) -> requests.Response:
    try:
        response = session.get(LOGIN_URL, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise PlaceSessionError("No se pudo abrir la página de acceso de PLACE.") from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        asegurar_sin_reto_acceso(response, code="PLACE_LOGIN_CHALLENGE")
        raise PlaceSessionError("No se pudo abrir la página de acceso de PLACE.") from exc
    asegurar_sin_reto_acceso(response, code="PLACE_LOGIN_CHALLENGE")
    soup = soup_from_response(response)
    password_input = soup.find("input", attrs={"type": "password"})
    form = password_input.find_parent("form") if isinstance(password_input, Tag) else None
    if not isinstance(form, Tag):
        raise PlaceStructureError("No se encontró el formulario de acceso de PLACE.")
    payload = build_form_payload(form)
    user_input = form.find("input", attrs={"name": "wps.portlets.userid"})
    if not isinstance(user_input, Tag) or not password_input.get("name"):
        raise PlaceStructureError("El formulario de acceso de PLACE ha cambiado.")
    payload[str(user_input["name"])] = username
    payload[str(password_input["name"])] = password
    action_url = urljoin(response.url, str(form.get("action") or response.url))
    try:
        response = session.post(action_url, data=payload, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise PlaceSessionError("PLACE no completó la autenticación.") from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        asegurar_sin_reto_acceso(response, code="PLACE_LOGIN_CHALLENGE")
        raise PlaceSessionError("PLACE no completó la autenticación.") from exc
    asegurar_sin_reto_acceso(response, code="PLACE_LOGIN_CHALLENGE")
    if "/wps/myportal/" not in response.url or "Finalizar sesión" not in response.text:
        raise PlaceAuthenticationError("PLACE no aceptó la cuenta configurada.")
    return response


def ensure_active_session(response: requests.Response) -> None:
    asegurar_sin_reto_acceso(response, code="PLACE_ACCESS_CHALLENGE")
    if "wps.portlets.userid" in response.text or "Iniciar sesión" in response.text:
        raise PlaceSessionError("La sesión de PLACE caducó durante la consulta.")


def find_link_by_text(soup: BeautifulSoup, text: str) -> Tag:
    wanted = normalized_key(text)
    for link in soup.find_all("a"):
        if normalized_key(link.get_text(" ", strip=True)) == wanted:
            return link
    raise PlaceStructureError(f"No se encontró la opción «{text}» en PLACE.")
