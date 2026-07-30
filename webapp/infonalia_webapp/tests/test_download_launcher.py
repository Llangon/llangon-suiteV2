import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_launcher_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "herramientas_python" / "Descargar_Licitacion.py"
    spec = importlib.util.spec_from_file_location("descargar_licitacion_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_detects_catalunya_urls() -> None:
    launcher = load_launcher_module()

    assert launcher.detectar_plataforma("https://contractaciopublica.cat/ca/detall") == "CATALUNYA"
    assert launcher.detectar_plataforma("https://www.contractaciopublica.cat/ca/detall") == "CATALUNYA"
    assert launcher.detectar_plataforma("contractaciopublica.cat/ca/detall") == "CATALUNYA"


def test_launcher_routes_catalunya_to_its_downloader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    launcher = load_launcher_module()
    url = "https://contractaciopublica.cat/ca/detall-publicacio/exemple"
    calls = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["Descargar_Licitacion.py", url])
    monkeypatch.setattr(
        launcher,
        "ejecutar",
        lambda script, argumentos, carpeta_destino: calls.append(
            (Path(script).name, argumentos, Path(carpeta_destino))
        ) or 0,
    )

    with pytest.raises(SystemExit) as exc_info:
        launcher.main()

    assert exc_info.value.code == 0
    assert calls == [("Descargar_Catalunya.py", [url], tmp_path)]


def test_launcher_detects_navarra_urls() -> None:
    launcher = load_launcher_module()

    assert launcher.detectar_plataforma(
        "https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod=ejemplo"
    ) == "NAVARRA"
    assert launcher.detectar_plataforma(
        "https://licitacionelectronica.navarra.es/licitador/licitadores/detalle/ejemplo/s"
    ) == "NAVARRA"


def test_launcher_detects_xunta_de_galicia_urls() -> None:
    launcher = load_launcher_module()

    assert launcher.detectar_plataforma(
        "https://www.contratosdegalicia.gal/licitacion?N=827794"
    ) == "XUNTA_DE_GALICIA"
    assert launcher.detectar_plataforma(
        "contratosdegalicia.gal/licitacion?N=827794"
    ) == "XUNTA_DE_GALICIA"


def test_launcher_routes_navarra_to_its_downloader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    launcher = load_launcher_module()
    url = "https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod=ejemplo"
    calls = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["Descargar_Licitacion.py", url])
    monkeypatch.setattr(
        launcher,
        "ejecutar",
        lambda script, argumentos, carpeta_destino: calls.append(
            (Path(script).name, argumentos, Path(carpeta_destino))
        ) or 0,
    )

    with pytest.raises(SystemExit) as exc_info:
        launcher.main()

    assert exc_info.value.code == 0
    assert calls == [("Descargar_Navarra.py", [url], tmp_path)]


@pytest.mark.parametrize(
    ("url", "platform", "script"),
    (
        ("https://contrataciondelestado.es/wps/poc", "PLACE", "Descargar_PLACE.py"),
        (
            "https://juntadeandalucia.es/temas/contratacion-publica/perfiles-licitaciones/detalle/1",
            "JUNTA_ANDALUCIA",
            "Descargar_JuntaAndalucia.py",
        ),
        (
            "https://contratos-publicos.comunidad.madrid/contrato-publico/1",
            "COMUNIDAD_MADRID",
            "Descargar_ComunidadMadrid.py",
        ),
        (
            "https://www.contratacion.euskadi.eus/anuncio_contratacion/1",
            "EUSKADI",
            "Descargar_Euskadi.py",
        ),
        (
            "https://contractaciopublica.cat/es/detall-publicacio/1",
            "CATALUNYA",
            "Descargar_Catalunya.py",
        ),
        (
            "https://hacienda.navarra.es/sicpportal/mtoAnunciosModalidad.aspx?cod=1",
            "NAVARRA",
            "Descargar_Navarra.py",
        ),
        (
            "https://www.contratosdegalicia.gal/licitacion?N=827794",
            "XUNTA_DE_GALICIA",
            "Descargar_XuntaGalicia.py",
        ),
    ),
)
def test_launcher_preserves_routing_for_every_operational_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    url: str,
    platform: str,
    script: str,
) -> None:
    launcher = load_launcher_module()
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["Descargar_Licitacion.py", url])
    monkeypatch.setattr(
        launcher,
        "ejecutar",
        lambda path, arguments, destination: calls.append(
            (Path(path).name, arguments, Path(destination))
        ) or 0,
    )

    with pytest.raises(SystemExit) as exc_info:
        launcher.main()

    assert launcher.detectar_plataforma(url) == platform
    assert exc_info.value.code == 0
    assert calls == [(script, [url], tmp_path)]


def test_launcher_honors_explicit_destination_without_forwarding_it_twice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    launcher = load_launcher_module()
    working_directory = tmp_path / "origen"
    destination = tmp_path / "destino"
    working_directory.mkdir()
    calls = []
    url = (
        "https://www.juntadeandalucia.es/haciendayadministracionpublica/apl/"
        "pdc-front-publico/perfiles-licitaciones/detalle-licitacion?idExpediente=944739"
    )
    monkeypatch.chdir(working_directory)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "Descargar_Licitacion.py",
            url,
            "--destino",
            str(destination),
            "--incluir-sellos",
        ],
    )
    monkeypatch.setattr(
        launcher,
        "ejecutar",
        lambda script, arguments, selected_destination: calls.append(
            (Path(script).name, arguments, Path(selected_destination))
        )
        or 0,
    )

    with pytest.raises(SystemExit) as exc_info:
        launcher.main()

    assert exc_info.value.code == 0
    assert calls == [
        (
            "Descargar_JuntaAndalucia.py",
            [url, "--incluir-sellos"],
            destination,
        )
    ]


def test_launcher_normal_download_never_persists_monitor_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    launcher = load_launcher_module()
    facade = tmp_path / "Descargar_PLACE.py"
    facade.write_text("# fake", encoding="utf-8")
    payload = {
        "platform": "PLACE",
        "source_url": "https://contrataciondelestado.es/wps/poc",
        "started_at": "2026-07-20T09:00:00",
        "finished_at": "2026-07-20T09:01:00",
        "status": "success",
        "capabilities": {"documents": True, "questions_and_answers": False},
        "artifacts": [
            {
                "name": "acta.pdf",
                "status": "created",
                "source_url": "https://example.test/acta.pdf",
                "path": "acta.pdf",
                "sha256": "abc",
                "role": "document",
            }
        ],
    }
    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="RESULTADO_ESTRUCTURADO=" + json.dumps(payload) + "\n",
            stderr="",
        ),
    )

    assert launcher.ejecutar(str(facade), [payload["source_url"]], str(tmp_path)) == 0
    assert not (tmp_path / ".llangon-monitor" / "technical_snapshot.json").exists()


def test_launcher_uses_utf8_for_downloader_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    launcher = load_launcher_module()
    facade = tmp_path / "Descargar_JuntaAndalucia.py"
    facade.write_text("# fake", encoding="utf-8")
    call = {}

    def fake_run(*args, **kwargs):
        call["args"] = args
        call["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="Licitación y cláusula\n", stderr="")

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    assert launcher.ejecutar(str(facade), ["https://example.test"], str(tmp_path)) == 0
    assert call["kwargs"]["encoding"] == "utf-8"
    assert call["kwargs"]["errors"] == "replace"
    assert call["kwargs"]["env"]["PYTHONIOENCODING"] == "utf-8"
    assert "Licitación y cláusula" in capsys.readouterr().out


def test_launcher_returns_recoverable_busy_code_without_starting_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    launcher = load_launcher_module()
    facade = tmp_path / "Descargar_PLACE.py"
    facade.write_text("# fake", encoding="utf-8")
    calls = 0

    def fake_run(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("El subproceso no debe iniciarse con la carpeta bloqueada")

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    with launcher.destination_lock(tmp_path, owner="monitor:test"):
        code = launcher.ejecutar(str(facade), ["https://example.test"], str(tmp_path))

    assert code == 75
    assert calls == 0
