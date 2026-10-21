from sqlalchemy import select
from app.database.db import session
from app.database.tables import ImportRecord

def seen(source_id):
    with session() as s:
        return s.scalar(select(ImportRecord.id).where(ImportRecord.source_id == source_id)) is not None

def record(source_id, url, title, status, score=None):
    with session() as s:
        s.add(ImportRecord(source_id=source_id, job_url=url, title=title, status=status, score=score))

def history():
    with session() as s:
        rows = s.scalars(select(ImportRecord).order_by(ImportRecord.id.desc())).all()
        return [{'source_id': r.source_id, 'job_url': r.job_url, 'title': r.title, 'status': r.status,
                 'score': r.score, 'processed_at': r.processed_at.isoformat()} for r in rows]