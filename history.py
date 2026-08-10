import json
from pathlib import Path

HISTORY_DIR = Path.home() / ".metatune"
HISTORY_FILE = HISTORY_DIR / "history.json"
MAX_HISTORY_ITEMS = 10


def load_history(path: Path = HISTORY_FILE) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(p) for p in data]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def add_to_history(entry: Path, history: list[str] | None = None, path: Path = HISTORY_FILE) -> list[str]:
    if history is None:
        history = load_history(path)
    entry_str = str(entry)
    history = [h for h in history if h != entry_str]
    history.insert(0, entry_str)
    history = history[:MAX_HISTORY_ITEMS]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return history
