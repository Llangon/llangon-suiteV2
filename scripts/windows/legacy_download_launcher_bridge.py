import os
import subprocess
import sys
from pathlib import Path


def suite_root() -> Path:
    configured = os.environ.get("LLANGON_SUITE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return (Path.home() / "Documents" / "Codex" / "Llangon-SuiteV2").resolve(strict=False)


def central_command(arguments=None) -> list[str]:
    root = suite_root()
    python_executable = root / ".venv" / "Scripts" / "python.exe"
    launcher = root / "herramientas_python" / "Descargar_Licitacion.py"

    if not python_executable.is_file():
        raise FileNotFoundError(f"No se encontro el Python de la app: {python_executable}")
    if not launcher.is_file():
        raise FileNotFoundError(f"No se encontro el descargador central de la app: {launcher}")

    return [str(python_executable), str(launcher), *(arguments or [])]


def main() -> int:
    try:
        command = central_command(sys.argv[1:])
    except FileNotFoundError as exc:
        print(exc, flush=True)
        return 1

    return subprocess.call(command, cwd=os.getcwd())


if __name__ == "__main__":
    raise SystemExit(main())
