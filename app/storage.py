from app.database.db import session
from app.database.tables import StoredFile

def put_file(key, data, content_type='application/octet-stream'):
    with session() as s:
        s.merge(StoredFile(key=key, content_type=content_type, data=data))

def get_file(key):
    with session() as s:
        row = s.get(StoredFile, key)
        if not row:
            raise FileNotFoundError(key)
        return bytes(row.data)

def delete_file(key):
    with session() as s:
        row = s.get(StoredFile, key)
        if row:
            s.delete(row)