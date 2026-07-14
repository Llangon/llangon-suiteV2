import importlib.util
import sys
from pathlib import Path

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
