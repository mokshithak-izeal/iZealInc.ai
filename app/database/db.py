import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

url = os.getenv('DATABASE_URL', 'sqlite:///data/jobagent.db')
for prefix in ('postgres://', 'postgresql://', 'postgresql+psycopg://'):
    if url.startswith(prefix):
        url = 'postgresql+psycopg2://' + url[len(prefix):]
        break
engine = create_engine(url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def migration_engine():
    migration_url = os.getenv('DATABASE_URL_UNPOOLED')
    if not migration_url:
        return engine
    for prefix in ('postgres://', 'postgresql://', 'postgresql+psycopg://'):
        if migration_url.startswith(prefix):
            migration_url = 'postgresql+psycopg2://' + migration_url[len(prefix):]
            break
    return create_engine(migration_url, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass

@contextmanager
def session():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()