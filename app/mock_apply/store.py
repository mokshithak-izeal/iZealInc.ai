from pathlib import Path
from datetime import datetime,timezone
import json
BASE=Path(__file__).resolve().parents[2];DB=BASE/'data'/'mock_submissions.json';DB.parent.mkdir(exist_ok=True)
def save_submission(data):
    rows=[]
    if DB.exists():
        try:rows=json.loads(DB.read_text(encoding='utf-8'))
        except Exception:pass
    item={**data,'submitted_at':datetime.now(timezone.utc).isoformat()};rows.append(item);DB.write_text(json.dumps(rows,indent=2),encoding='utf-8');return item
def submissions():
    if not DB.exists():return []
    try:return json.loads(DB.read_text(encoding='utf-8'))
    except Exception:return []
