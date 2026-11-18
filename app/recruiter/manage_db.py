"""Usage: python -m app.recruiter.manage_db upgrade|drop"""

import argparse

from app.database.db import Base, engine, migration_engine
from app.database.schema_migrations import (
    migrate_legacy_recruiter_data,
    stage_legacy_recruiter_tables,
)
from app.recruiter import models

TABLES = [
    models.RecruiterJob.__table__,
    models.RecruiterCandidate.__table__,
    models.RecruiterMatch.__table__,
    models.RecruiterSubmission.__table__,
    models.RecruiterIntegration.__table__,
    models.RecruiterSetting.__table__,
]


def upgrade(bind=None) -> None:
    owns_engine = bind is None
    bind = bind or migration_engine()
    try:
        stage_legacy_recruiter_tables(bind)
        Base.metadata.create_all(bind=bind, tables=TABLES)
        migrate_legacy_recruiter_data(bind)
    finally:
        if owns_engine and bind is not engine:
            bind.dispose()


def drop(bind=None) -> None:
    owns_engine = bind is None
    bind = bind or migration_engine()
    try:
        Base.metadata.drop_all(bind=bind, tables=TABLES)
    finally:
        if owns_engine and bind is not engine:
            bind.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Create or drop the recruiter feature database tables.'
    )
    parser.add_argument('command', choices=('upgrade', 'drop'))
    command = parser.parse_args().command

    if command == 'upgrade':
        upgrade()
        print('Recruiter tables created and legacy recruiter data migrated.')
    else:
        drop()
        print('Recruiter tables dropped.')


if __name__ == '__main__':
    main()
