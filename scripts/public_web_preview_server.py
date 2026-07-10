from __future__ import annotations

import argparse
import contextlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class FirebaseLikeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, **kwargs) -> None:
        self.public_root = Path(directory).resolve()
        super().__init__(*args, directory=str(self.public_root), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_head(self):
        requested = self._requested_path()
        if requested and requested.is_file():
            return super().send_head()

        if requested and requested.is_dir():
            index = requested / "index.html"
            if index.is_file():
                self.path = self._path_for(index)
                return super().send_head()

        if self._should_rewrite_to_index():
            self.path = "/index.html"
            return super().send_head()

        return super().send_head()

    def _requested_path(self) -> Path | None:
        raw_path = unquote(urlsplit(self.path).path)
        relative = raw_path.lstrip("/")
        candidate = (self.public_root / relative).resolve()
        try:
            candidate.relative_to(self.public_root)
        except ValueError:
            return None
        return candidate

    def _should_rewrite_to_index(self) -> bool:
        raw_path = unquote(urlsplit(self.path).path)
        name = Path(raw_path).name
        return "." not in name

    def _path_for(self, file_path: Path) -> str:
        return "/" + file_path.relative_to(self.public_root).as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Firebase public site locally.")
    parser.add_argument("--directory", required=True, help="Public Firebase directory to serve.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", default=5500, type=int, help="Port to bind.")
    args = parser.parse_args()

    public_root = Path(args.directory).resolve()
    if not public_root.is_dir():
        raise SystemExit(f"Public directory does not exist: {public_root}")

    handler = lambda *handler_args, **handler_kwargs: FirebaseLikeHandler(  # noqa: E731
        *handler_args,
        directory=str(public_root),
        **handler_kwargs,
    )

    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
