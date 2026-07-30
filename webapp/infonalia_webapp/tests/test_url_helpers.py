from __future__ import annotations

import importlib
import sys

from webapp.infonalia_webapp.url_helpers import detectar_plataforma, normalize_url, should_update_url


def test_url_helpers_import_does_not_import_app_or_side_effect_modules() -> None:
    sys.modules.pop("webapp.infonalia_webapp.url_helpers", None)
    app_was_imported = "webapp.infonalia_webapp.app" in sys.modules
    before = set(sys.modules)

    importlib.import_module("webapp.infonalia_webapp.url_helpers")

    added = set(sys.modules) - before
    assert "app" not in sys.modules
    assert ("webapp.infonalia_webapp.app" in sys.modules) is app_was_imported
    assert not {"sqlite3", "requests", "http.server", "socketserver", "subprocess"} & added


def test_normalize_url_preserves_existing_backend_rules() -> None:
    assert normalize_url("") == ""
    assert normalize_url("<http://>") == ""
    assert normalize_url("https://example.test/a") == "https://example.test/a"
    assert normalize_url("mailto:info@example.test") == "mailto:info@example.test"
    assert normalize_url("//example.test/a") == "https://example.test/a"
    assert normalize_url("example.test/a") == "https://example.test/a"
    assert normalize_url("javascript:alert(1)") == "javascript:alert(1)"


def test_should_update_url_preserves_existing_rules() -> None:
    assert should_update_url("", "https://example.test") is True
    assert should_update_url("example.test/a", "https://example.test/a") is True
    assert should_update_url("https://example.test/a", "https://example.test/a") is False
    assert should_update_url("https://example.test/a", "") is False


def test_detectar_plataforma_preserves_known_platforms() -> None:
    assert detectar_plataforma("https://contrataciondelestado.es/wps/portal") == "PLACE"
    assert detectar_plataforma("https://www.juntadeandalucia.es/pdc-front-publico") == "Junta Andalucia"
    assert detectar_plataforma("https://contratos-publicos.comunidad.madrid/contrato") == "Comunidad Madrid"
    assert detectar_plataforma("https://www.contratacion.euskadi.eus/anuncio") == "Euskadi"
    assert detectar_plataforma("https://contractaciopublica.cat/ca/detall") == "Catalunya"
    assert detectar_plataforma("https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod=1") == "Navarra"
    assert detectar_plataforma("https://licitacionelectronica.navarra.es/licitador/licitadores/detalle/1/s") == "Navarra"
    assert detectar_plataforma("https://www.contratosdegalicia.gal/licitacion?N=827794") == "Xunta de Galicia"
    assert detectar_plataforma("https://example.test") == ""
