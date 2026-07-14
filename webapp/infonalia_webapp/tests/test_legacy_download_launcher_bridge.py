import importlib.util
from pathlib import Path


def load_bridge_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "windows" / "legacy_download_launcher_bridge.py"
    spec = importlib.util.spec_from_file_location("legacy_download_launcher_bridge_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bridge_calls_central_app_launcher(monkeypatch, tmp_path: Path) -> None:
    bridge = load_bridge_module()
    python_executable = tmp_path / ".venv" / "Scripts" / "python.exe"
    launcher = tmp_path / "herramientas_python" / "Descargar_Licitacion.py"
    python_executable.parent.mkdir(parents=True)
    launcher.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    launcher.write_text("", encoding="utf-8")
    calls = []

    monkeypatch.setenv("LLANGON_SUITE_ROOT", str(tmp_path))
    monkeypatch.setattr(bridge.sys, "argv", ["Descargar_Licitacion.py", "https://example.test/ficha"])
    monkeypatch.setattr(
        bridge.subprocess,
        "call",
        lambda command, cwd: calls.append((command, cwd)) or 0,
    )

    assert bridge.main() == 0
    assert calls == [
        (
            [str(python_executable), str(launcher), "https://example.test/ficha"],
            bridge.os.getcwd(),
        )
    ]


def test_bridge_fails_clearly_when_app_runtime_is_missing(monkeypatch, tmp_path: Path, capsys) -> None:
    bridge = load_bridge_module()
    monkeypatch.setenv("LLANGON_SUITE_ROOT", str(tmp_path))

    assert bridge.main() == 1
    assert "No se encontro el Python de la app" in capsys.readouterr().out
