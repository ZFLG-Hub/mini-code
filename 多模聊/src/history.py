import json
import uuid
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".duomoliao" / "sessions"


def _ensure_dir():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def create_session(model_key):
    _ensure_dir()
    session_id = uuid.uuid4().hex[:8]
    session = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "model": model_key,
        "messages": [],
    }
    _save_session(session)
    return session


def _filepath(session_id):
    return SESSIONS_DIR / f"{session_id}.json"


def _save_session(session):
    _ensure_dir()
    session["updated_at"] = datetime.now().isoformat()
    path = _filepath(session["session_id"])
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
    except UnicodeEncodeError:
        sanitized = _sanitize(session)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2, ensure_ascii=False)


def _sanitize(obj):
    if isinstance(obj, str):
        return obj.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def save_session(session):
    _save_session(session)


def load_session(session_id):
    path = _filepath(session_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_sessions():
    _ensure_dir()
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
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
            "model": data.get("model", "unknown"),
            "messages": msg_count,
            "preview": preview,
            "updated": data.get("updated_at", ""),
        })
    return sessions


def delete_session(session_id):
    path = _filepath(session_id)
    if path.exists():
        path.unlink()
        return True
    return False
