from sqlalchemy import select
from app.database.db import session
from app.database.tables import Application

def list_applications():
    with session() as s:
        rows = s.scalars(select(Application).order_by(Application.id.desc())).all()
        return [{**r.data, 'applied_at': r.applied_at.isoformat()} for r in rows]

def save_application(item: dict):
    url = (item.get('job_url') or '').strip()
    with session() as s:
        if url and s.scalar(select(Application.id).where(Application.job_url == url)) is not None:
            return None
        row = Application(job_url=url, data=dict(item))
        s.add(row)
        s.flush()
        return {**item, 'applied_at': row.applied_at.isoformat()}