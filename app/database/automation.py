from pathlib import Path
from datetime import datetime, timezone
import json
BASE=Path(__file__).resolve().parents[2]; DB=BASE/'data'/'automation_imports.json'; DB.parent.mkdir(exist_ok=True)
def _load():
    if not DB.exists(): return []
    try:return json.loads(DB.read_text(encoding='utf-8'))
    except Exception:return []
def _save(rows):DB.write_text(json.dumps(rows,indent=2),encoding='utf-8')
def seen(source_id):return any(x.get('source_id')==source_id for x in _load())
def record(source_id,url,title,status,score=None):
    rows=_load(); rows.append({'source_id':source_id,'job_url':url,'title':title,'status':status,'score':score,'processed_at':datetime.now(timezone.utc).isoformat()});_save(rows)
def history():return list(reversed(_load()))
