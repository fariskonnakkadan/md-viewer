#!/usr/bin/env python3
import os
import sys
import http.server
import socketserver
import urllib.parse
import webbrowser
import signal
from pathlib import Path

PORT = 7429


class DirectoryHandler(http.server.SimpleHTTPRequestHandler):
    ICONS = {".md": "📝"}

    def __init__(self, *args, base_dir=None, **kwargs):
        self.base_dir = base_dir or os.getcwd()
        super().__init__(*args, **kwargs)

    # ───────────────────────── helpers ─────────────────────────
    @staticmethod
    def _pretty(name: str) -> str:
        return name.replace("-", " ").replace("_", " ").title()

    def _icon_for(self, path: Path) -> str:
        return "📁" if path.is_dir() else self.ICONS.get(path.suffix.lower(), "📄")

    # ───────────────────────── routing ─────────────────────────
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        file_path = os.path.join(self.base_dir, parsed.path.lstrip("/"))

        if not os.path.commonpath([self.base_dir, os.path.abspath(file_path)]) == self.base_dir:
            self.send_error(403)
            return

        if os.path.isfile(file_path):
            if file_path.endswith(".md"):
                self.serve_markdown(file_path)
            else:
                # non‑MD files are not listed, but if someone types the exact URL we still serve it
                self.serve_file(file_path)
        elif os.path.isdir(file_path):
            self.serve_directory(file_path)
        else:
            self.send_error(404)

    # ─────────────────── markdown & file serving ───────────────
    def serve_markdown(self, file_path):
        try:
            import markdown
            with open(file_path, "r", encoding="utf-8") as f:
                md = f.read()
            body = markdown.markdown(md, extensions=["codehilite", "fenced_code"])
            title = self._pretty(os.path.basename(file_path))
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>MD Viewer - {title}</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:800px;margin:40px auto;padding:0 20px}}
 .nav{{margin-bottom:20px;padding-bottom:10px;border-bottom:1px solid #eee}}
 .nav a{{color:#06c;text-decoration:none}}
 pre{{background:#f5f5f5;padding:10px;border-radius:4px;overflow-x:auto}}
 code{{background:#f5f5f5;padding:2px 4px;border-radius:2px}}
 blockquote{{border-left:4px solid #ddd;margin:0;padding-left:20px;color:#666}}
</style></head>
<body>
 <h1>📘 MD Viewer</h1>
 <div class="nav"><a href="/">← Back to directory</a></div>
 {body}
</body></html>"""
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        except ImportError:
            # plain text fallback
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode())

    def serve_file(self, file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(500)

    # ───────────────────── directory listing ───────────────────
    def serve_directory(self, dir_path):
        try:
            rows = []
            for item in sorted(os.listdir(dir_path)):
                if item.startswith("."):
                    continue  # hide dotfiles/dirs
                item_path = Path(dir_path, item)

                # show dirs always; show files only if .md
                if item_path.is_file() and item_path.suffix.lower() != ".md":
                    continue

                rel = urllib.parse.quote(os.path.relpath(item_path, self.base_dir))
                label = self._pretty(item)
                icon = self._icon_for(item_path)
                suffix = "/" if item_path.is_dir() else ""
                rows.append(f'<li>{icon} <a href="/{rel}">{label}{suffix}</a></li>')

            current = os.path.relpath(dir_path, self.base_dir)
            title = self._pretty("." if current == "." else current)
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>MD Viewer - {title}</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:40px}}
 ul{{list-style:none;padding:0}}
 li{{padding:8px 0;border-bottom:1px solid #f5f5f5}}
 a{{text-decoration:none;color:#333}}
 a:hover{{text-decoration:underline}}
</style></head>
<body>
 <h1>📘 MD Viewer</h1>
 <h2>📂 {title}</h2>
 <ul>{''.join(rows)}</ul>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        except Exception:
            self.send_error(500)


# ───────────────────── server bootstrap ──────────────────────
def main():
    target = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not os.path.isdir(target):
        print(f"Error: {target} is not a directory"); sys.exit(1)
    os.chdir(target)

    handler = lambda *a, **kw: DirectoryHandler(*a, base_dir=target, **kw)
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"Serving {target} at {url}")
        webbrowser.open(url)

        def shutdown(sig, frame):
            print("\nShutting down server...")
            httpd.shutdown(); sys.exit(0)
        signal.signal(signal.SIGINT, shutdown)

        print("Press Ctrl+C to stop the server")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
