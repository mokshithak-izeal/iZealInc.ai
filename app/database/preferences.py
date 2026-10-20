from pathlib import Path
import json
BASE=Path(__file__).resolve().parents[2]; DB=BASE/'data'/'preferences.json'; DB.parent.mkdir(exist_ok=True)
DEFAULT={'preferred_role':'','preferred_locations':[],'work_modes':[],'minimum_match':80,'excluded_companies':[]}
def load_preferences():
    if not DB.exists(): return dict(DEFAULT)
    try:return {**DEFAULT,**json.loads(DB.read_text(encoding='utf-8'))}
    except Exception:return dict(DEFAULT)
def save_preferences(data):
    out={**DEFAULT,**data};out['minimum_match']=max(0,min(100,int(out.get('minimum_match',80))));DB.write_text(json.dumps(out,indent=2),encoding='utf-8');return out
