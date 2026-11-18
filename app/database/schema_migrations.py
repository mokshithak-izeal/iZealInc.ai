import json
from datetime import datetime

from sqlalchemy import MetaData, Table, insert, inspect, select
from sqlalchemy.engine import Engine

from app.recruiter.models import (
    RecruiterCandidate,
    RecruiterIntegration,
    RecruiterJob,
    RecruiterMatch,
    RecruiterSetting,
    RecruiterSubmission,
)

LEGACY_TABLES = (
    'recruiter_matches',
    'recruiter_submissions',
    'recruiter_settings',
    'recruiter_jobs',
)
LEGACY_PREFIX = 'legacy_v1_'


def stage_legacy_recruiter_tables(engine: Engine) -> None:
    inspector = inspect(engine)
    current_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name in LEGACY_TABLES:
            legacy_name = f'{LEGACY_PREFIX}{table_name}'
            if table_name not in current_tables or legacy_name in current_tables:
                continue
            column_names = {column['name'] for column in inspector.get_columns(table_name)}
            if 'owner_key' not in column_names:
                connection.exec_driver_sql(
                    f'ALTER TABLE {table_name} RENAME TO {legacy_name}'
                )


def upgrade_recruiter_candidate_profiles(engine: Engine) -> None:
    inspector = inspect(engine)
    if 'recruiter_candidates' not in inspector.get_table_names():
        return
    existing_columns = {
        column['name']
        for column in inspector.get_columns('recruiter_candidates')
    }
    existing_indexes = {
        index['name']
        for index in inspector.get_indexes('recruiter_candidates')
    }
    new_columns = {
        'resume_candidate_id': 'VARCHAR(32)',
        'profile': 'JSON',
        'work_authorization': "VARCHAR(120) NOT NULL DEFAULT ''",
        'notes': "TEXT NOT NULL DEFAULT ''",
    }
    with engine.begin() as connection:
        for name, column_type in new_columns.items():
            if name not in existing_columns:
                connection.exec_driver_sql(
                    f'ALTER TABLE recruiter_candidates ADD COLUMN {name} {column_type}'
                )
        if 'ix_recruiter_candidates_resume_candidate_id' not in existing_indexes:
            connection.exec_driver_sql(
                'CREATE INDEX ix_recruiter_candidates_resume_candidate_id '
                'ON recruiter_candidates (resume_candidate_id)'
            )


def _legacy_rows(connection, table_name: str) -> list[dict]:
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names():
        return []
    table = Table(table_name, MetaData(), autoload_with=connection)
    return [dict(row) for row in connection.execute(select(table)).mappings()]


def _value(row: dict, key: str, fallback=None):
    value = row.get(key, fallback)
    return fallback if value is None else value


def _skills_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        names = [
            item.get('name', '') if isinstance(item, dict) else str(item)
            for item in value
        ]
        return ', '.join(name.strip() for name in names if name.strip())
    return ''


def _datetime(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def migrate_legacy_recruiter_data(engine: Engine) -> None:
    legacy_names = {f'{LEGACY_PREFIX}{name}' for name in LEGACY_TABLES}
    if not legacy_names.intersection(inspect(engine).get_table_names()):
        return

    with engine.begin() as connection:
        legacy_jobs = _legacy_rows(connection, f'{LEGACY_PREFIX}recruiter_jobs')
        legacy_matches = _legacy_rows(connection, f'{LEGACY_PREFIX}recruiter_matches')
        legacy_submissions = _legacy_rows(connection, f'{LEGACY_PREFIX}recruiter_submissions')
        legacy_settings = _legacy_rows(connection, f'{LEGACY_PREFIX}recruiter_settings')

        job_ids: dict[tuple[str, str], int] = {}
        candidate_ids: dict[tuple[str, str], int] = {}

        for old in legacy_jobs:
            owner_key = str(_value(old, 'recruiter_id', ''))
            if not owner_key:
                continue
            values = {
                'owner_key': owner_key,
                'title': _value(old, 'title', ''),
                'company': _value(old, 'company', ''),
                'location': _value(old, 'location', 'Remote'),
                'employment_type': _value(old, 'employment_type', 'Full Time'),
                'description': _value(old, 'description', ''),
                'required_skills': _skills_text(_value(old, 'required_skills', [])),
                'source': _value(old, 'source', 'Manual'),
                'external_id': _value(old, 'external_id'),
                'minimum_experience_years': _value(old, 'minimum_experience_years'),
                'status': _value(old, 'status', 'active'),
                'created_at': _datetime(_value(old, 'created_at', datetime.utcnow())),
            }
            result = connection.execute(insert(RecruiterJob.__table__).values(**values))
            job_ids[(owner_key, str(old['id']))] = result.inserted_primary_key[0]

        candidate_table = RecruiterCandidate.__table__
        candidate_source = None
        if 'candidates' in inspect(connection).get_table_names():
            candidate_source = Table('candidates', MetaData(), autoload_with=connection)
        used_emails: set[tuple[str, str]] = set()
        candidate_rows = (
            connection.execute(select(candidate_source)).mappings()
            if candidate_source is not None
            else []
        )
        for old in candidate_rows:
            old = dict(old)
            profile = old.get('profile') or {}
            owner_key = str(_value(old, 'uploaded_by', ''))
            if not owner_key:
                continue
            email = str(profile.get('email') or f"legacy-{old['id']}@migrated.invalid").strip()
            email_key = (owner_key, email.casefold())
            if email_key in used_emails:
                email = f"legacy-{old['id']}@migrated.invalid"
                email_key = (owner_key, email.casefold())
            used_emails.add(email_key)
            technical_skills = profile.get('technical_skills') or []
            skill_names = _skills_text(technical_skills)
            years = profile.get('total_experience_years')
            values = {
                'owner_key': owner_key,
                'name': old.get('name') or profile.get('candidate_name') or 'Unknown candidate',
                'email': email,
                'location': profile.get('location') or '',
                'years_experience': years if years is not None else 0,
                'skills': skill_names,
                'availability': profile.get('availability') or 'Available',
                'resume_id': None,
                'resume_candidate_id': old['id'],
                'current_role': profile.get('current_role') or '',
                'profile': {
                    key: value for key, value in profile.items()
                    if not key.startswith('_')
                },
                'work_authorization': profile.get('work_authorization') or '',
                'notes': '',
                'created_at': _datetime(old.get('created_at') or datetime.utcnow()),
            }
            result = connection.execute(insert(candidate_table).values(**values))
            candidate_ids[(owner_key, str(old['id']))] = result.inserted_primary_key[0]

        for old in legacy_matches:
            owner_key = str(_value(old, 'recruiter_id', ''))
            job_id = job_ids.get((owner_key, str(old.get('job_id'))))
            candidate_id = candidate_ids.get((owner_key, str(old.get('candidate_id'))))
            if not job_id or not candidate_id:
                continue
            connection.execute(insert(RecruiterMatch.__table__).values(
                owner_key=owner_key,
                job_id=job_id,
                candidate_id=candidate_id,
                score=_value(old, 'score', 0),
                matched_skills=_skills_text(_value(old, 'matched_skills', [])),
                missing_skills=_skills_text(_value(old, 'missing_skills', [])),
                explanation=_value(old, 'explanation', ''),
                shortlisted=_value(old, 'shortlisted', False),
                created_at=_datetime(_value(old, 'created_at', datetime.utcnow())),
            ))

        for old in legacy_submissions:
            owner_key = str(_value(old, 'recruiter_id', ''))
            job_id = job_ids.get((owner_key, str(old.get('job_id'))))
            candidate_id = candidate_ids.get((owner_key, str(old.get('candidate_id'))))
            if not job_id or not candidate_id:
                continue
            connection.execute(insert(RecruiterSubmission.__table__).values(
                owner_key=owner_key,
                job_id=job_id,
                candidate_id=candidate_id,
                vendor=_value(old, 'vendor', ''),
                consent_share=_value(old, 'consent_share', False),
                consent_contact=_value(old, 'consent_contact', False),
                notes=_value(old, 'notes', ''),
                status=_value(old, 'status', 'submitted'),
                created_at=_datetime(_value(old, 'created_at', datetime.utcnow())),
            ))

        for old in legacy_settings:
            owner_key = str(_value(old, 'recruiter_id', ''))
            if not owner_key:
                continue
            connection.execute(insert(RecruiterSetting.__table__).values(
                owner_key=owner_key,
                ai_model=_value(old, 'ai_model', 'gemini-2.5-flash'),
                match_threshold=_value(old, 'match_threshold', 70),
                created_at=_datetime(_value(old, 'created_at', datetime.utcnow())),
            ))
            raw_integrations = _value(old, 'integrations', [])
            if isinstance(raw_integrations, str):
                try:
                    raw_integrations = json.loads(raw_integrations)
                except json.JSONDecodeError:
                    raw_integrations = []
            if isinstance(raw_integrations, dict):
                raw_integrations = [
                    {'provider': name, **config} if isinstance(config, dict)
                    else {'provider': name, 'enabled': bool(config)}
                    for name, config in raw_integrations.items()
                ]
            for integration in raw_integrations if isinstance(raw_integrations, list) else []:
                if not isinstance(integration, dict) or not integration.get('provider'):
                    continue
                config_json = integration.get('config_json', '{}')
                if not isinstance(config_json, str):
                    config_json = json.dumps(config_json)
                connection.execute(insert(RecruiterIntegration.__table__).values(
                    owner_key=owner_key,
                    provider=str(integration['provider']),
                    enabled=bool(integration.get('enabled', False)),
                    config_json=config_json,
                    created_at=_datetime(_value(old, 'created_at', datetime.utcnow())),
                ))

        inspector = inspect(connection)
        for table_name in (
            f'{LEGACY_PREFIX}recruiter_matches',
            f'{LEGACY_PREFIX}recruiter_submissions',
            f'{LEGACY_PREFIX}recruiter_settings',
            f'{LEGACY_PREFIX}recruiter_jobs',
        ):
            if table_name in inspector.get_table_names():
                connection.exec_driver_sql(f'DROP TABLE {table_name}')
