from pathlib import Path
from datetime import datetime,timezone
from app.database.state import load_state, update_state

BASE=Path(__file__).resolve().parents[2];DB=BASE/'data'/'mock_submissions.json'
def save_submission(data):
    item={**data,'submitted_at':datetime.now(timezone.utc).isoformat()}
    def update(rows):
        rows.append(item)
        return rows,item
    return update_state('mock_submissions',DB,[],update)
def submissions():
    return load_state('mock_submissions',DB,[])
