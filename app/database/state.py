import copy
import json
import os
from contextlib import closing
from pathlib import Path
from threading import Lock
from typing import Callable, TypeVar

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local")

T = TypeVar("T")
_local_lock = Lock()
_schema_lock = Lock()
_schema_ready = False
_migration_file = Path(__file__).resolve().parent / "migrations" / "001_jobagent_state.sql"


def _database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


def _read_legacy(path: Path, default: T) -> T:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_legacy(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        url = os.getenv("DATABASE_URL_UNPOOLED") or _database_url()
        if not url:
            return
        migration = _migration_file.read_text(encoding="utf-8")
        with closing(psycopg2.connect(url)) as connection:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(migration)
        _schema_ready = True


def load_state(key: str, path: Path, default: T) -> T:
    url = _database_url()
    if not url:
        return _read_legacy(path, default)

    _ensure_schema()
    with closing(psycopg2.connect(url)) as connection:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM jobagent_state WHERE state_key = %s",
                    (key,),
                )
                row = cursor.fetchone()
                if row is not None:
                    return row[0]

                initial = _read_legacy(path, default)
                cursor.execute(
                    """
                    INSERT INTO jobagent_state (state_key, payload)
                    VALUES (%s, %s)
                    ON CONFLICT (state_key) DO NOTHING
                    """,
                    (key, Json(initial)),
                )
                cursor.execute(
                    "SELECT payload FROM jobagent_state WHERE state_key = %s",
                    (key,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(f"Unable to initialize persisted state: {key}")
                return row[0]


def save_state(key: str, path: Path, value: object) -> None:
    url = _database_url()
    if not url:
        with _local_lock:
            _write_legacy(path, value)
        return

    _ensure_schema()
    with closing(psycopg2.connect(url)) as connection:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobagent_state (state_key, payload)
                    VALUES (%s, %s)
                    ON CONFLICT (state_key) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (key, Json(value)),
                )


def update_state(
    key: str,
    path: Path,
    default: T,
    update: Callable[[T], tuple[T, T]],
) -> T:
    url = _database_url()
    if not url:
        with _local_lock:
            state = _read_legacy(path, default)
            state, result = update(state)
            _write_legacy(path, state)
            return result

    _ensure_schema()
    with closing(psycopg2.connect(url)) as connection:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (key,),
                )
                cursor.execute(
                    "SELECT payload FROM jobagent_state WHERE state_key = %s FOR UPDATE",
                    (key,),
                )
                row = cursor.fetchone()
                state = row[0] if row is not None else _read_legacy(path, default)
                state, result = update(state)
                cursor.execute(
                    """
                    INSERT INTO jobagent_state (state_key, payload)
                    VALUES (%s, %s)
                    ON CONFLICT (state_key) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (key, Json(state)),
                )
                return result
