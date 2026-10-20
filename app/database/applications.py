from pathlib import Path
import json
from datetime import datetime, timezone
BASE_DIR = Path(__file__).resolve().parents[2]
DB = BASE_DIR / "data" / "applications.json"
DB.parent.mkdir(exist_ok=True)

def _load():
    if not DB.exists(): return []
    try: return json.loads(DB.read_text(encoding="utf-8"))
    except Exception: return []

def list_applications(): return _load()

def save_application(item: dict):
    rows = _load(); url = (item.get("job_url") or "").strip()
    if url and any((r.get("job_url") or "").strip() == url for r in rows):
        return None
    item = dict(item); item["applied_at"] = datetime.now(timezone.utc).isoformat(); rows.insert(0, item)
    DB.write_text(json.dumps(rows, indent=2), encoding="utf-8"); return item
