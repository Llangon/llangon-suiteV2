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


def test_launcher_normal_download_persists_structured_monitor_baseline(
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
    assert (tmp_path / ".llangon-monitor" / "technical_snapshot.json").is_file()
