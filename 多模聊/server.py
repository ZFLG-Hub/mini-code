#!/usr/bin/env python3
"""多模聊 Web Server — serves the chat UI and proxies LLM API calls with SSE streaming."""

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import uuid
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config as cfg
from src.backends.openai import OpenAIBackend
from src.backends.claude import ClaudeBackend
from src.backends.gemini import GeminiBackend
from src.backends.deepseek import DeepSeekBackend

BACKEND_CLASSES = {
    "openai": OpenAIBackend,
    "claude": ClaudeBackend,
    "gemini": GeminiBackend,
    "deepseek": DeepSeekBackend,
}

STATIC_DIR = Path(__file__).parent / "static"
SESSIONS_DIR = Path.home() / ".duomoliao_web" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_sessions():
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            msg_count = len(data.get("messages", []))
            preview = ""
            for msg in data.get("messages", []):
                if msg["role"] == "user":
                    preview = msg["content"][:60]
                    break
            sessions.append({
                "id": data["session_id"],
                "title": data.get("title", preview[:30] or "新对话"),
                "model": data.get("model", "unknown"),
                "messages": msg_count,
                "preview": preview,
                "updated": data.get("updated_at", ""),
            })
        except Exception:
            pass
    return sessions


def save_session(session):
    session["updated_at"] = datetime.now().isoformat()
    path = SESSIONS_DIR / f"{session['session_id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)


def load_session(session_id):
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_session_file(session_id):
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif parsed.path == "/api/sessions":
            self._send_json(load_sessions())
        elif parsed.path == "/api/models":
            config = cfg.load_config()
            models = []
            for key, info in config.get("models", {}).items():
                models.append({
                    "key": key,
                    "backend": info["backend"],
                    "model": info["model"],
                })
            self._send_json(models)
        elif parsed.path.startswith("/api/session/"):
            sid = parsed.path.split("/")[-1]
            session = load_session(sid)
            if session:
                self._send_json(session)
            else:
                self._send_json({"error": "session not found"}, 404)
        elif parsed.path == "/api/config":
            config = cfg.load_config()
            keys = config.get("api_keys", {})
            masked = {}
            for k, v in keys.items():
                masked[k] = True
            self._send_json({
                "default_model": config.get("default_model", ""),
                "max_history": config.get("max_history_messages", 10),
                "api_keys_configured": masked,
            })
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/chat":
            self._handle_chat()
        elif parsed.path == "/api/session":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len).decode("utf-8"))
            session = body.get("session", {})
            if not session.get("session_id"):
                session["session_id"] = uuid.uuid4().hex[:8]
                session["created_at"] = datetime.now().isoformat()
            if not session.get("title"):
                for msg in session.get("messages", []):
                    if msg["role"] == "user":
                        session["title"] = msg["content"][:30]
                        break
            save_session(session)
            self._send_json({"ok": True, "session_id": session["session_id"]})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/session/"):
            sid = parsed.path.split("/")[-1]
            ok = delete_session_file(sid)
            self._send_json({"ok": ok})
        else:
            self._send_json({"error": "not found"}, 404)

    def _serve_static(self, filename, content_type):
        path = STATIC_DIR / filename
        if not path.exists():
            self._send_json({"error": "file not found"}, 404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _handle_chat(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_len).decode("utf-8"))

        messages = body.get("messages", [])
        model_key = body.get("model_key", "")
        api_keys = body.get("api_keys", {})

        config = cfg.load_config()
        info = cfg.get_model_info(config, model_key)
        if not info:
            self._send_json({"error": f"unknown model: {model_key}"}, 400)
            return

        api_key = api_keys.get(info["backend"]) or cfg.get_api_key(config, info["backend"])
        if not api_key:
            self._send_json({"error": f"no API key for {info['backend']}"}, 400)
            return

        max_tokens = config.get("max_output_tokens", 4096)
        backend_cls = BACKEND_CLASSES[info["backend"]]
        backend = backend_cls(info["model"], api_key, max_tokens)

        # Trim history
        max_history = config.get("max_history_messages", 20)
        if len(messages) > max_history:
            system_msgs = [m for m in messages if m["role"] == "system"]
            other_msgs = [m for m in messages if m["role"] != "system"]
            messages = system_msgs + other_msgs[-max_history:]

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()

        try:
            for chunk in backend.chat(messages, stream=True):
                event = json.dumps({"content": chunk}, ensure_ascii=False)
                self.wfile.write(f"data: {event}\n\n".encode("utf-8"))
                self.wfile.flush()
            self.wfile.write(f"data: {json.dumps({'done': True})}\n\n".encode("utf-8"))
            self.wfile.flush()
        except Exception as e:
            error_event = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(f"data: {error_event}\n\n".encode("utf-8"))
            self.wfile.flush()


def main():
    port = 8080
    server = HTTPServer(("127.0.0.1", port), ChatHandler)
    print(f"\n  多模聊 Web 已启动!")
    print(f"  打开浏览器访问: http://127.0.0.1:{port}")
    print(f"  按 Ctrl+C 停止服务器\n")

    import webbrowser
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
