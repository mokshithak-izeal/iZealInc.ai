from app.database.db import session
from app.database.tables import Preference

DEFAULT = {'preferred_role': '', 'preferred_locations': [], 'work_modes': [],
           'minimum_match': 80, 'excluded_companies': []}

def load_preferences():
    with session() as s:
        row = s.get(Preference, 1)
        return {**DEFAULT, **(row.data if row else {})}

def save_preferences(data):
    out = {**DEFAULT, **data}
    out['minimum_match'] = max(0, min(100, int(out.get('minimum_match', 80))))
    with session() as s:
        row = s.get(Preference, 1)
        if row:
            row.data = out
        else:
            s.add(Preference(id=1, data=out))
    return out