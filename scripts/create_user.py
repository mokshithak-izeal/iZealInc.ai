"""Create a user, or reset the password of an existing one.

Run from the project folder:  python -m scripts.create_user
"""
import getpass
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import select
from app.auth import hash_password
from app.database.db import Base, engine, session
from app.database.tables import User

Base.metadata.create_all(engine)
email = input('Email: ').strip().lower()
with session() as s:
    existing = s.scalar(select(User).where(User.email == email))
    if existing:
        if input('That user exists. Reset the password and activate the account? (y/n): ').strip().lower() != 'y':
            raise SystemExit('No changes made.')
        password = getpass.getpass('New password (10+ characters): ')
        if len(password) < 10:
            raise SystemExit('The password must be at least 10 characters.')
        existing.password_hash = hash_password(password)
        existing.is_active = True
        print('Password reset and account activated.')
    else:
        name = input('Full name: ').strip()
        role = input('Role (admin/recruiter): ').strip().lower()
        password = getpass.getpass('Password (10+ characters): ')
        if role not in {'admin', 'recruiter'} or len(password) < 10:
            raise SystemExit('Role must be admin or recruiter, and the password at least 10 characters.')
        s.add(User(email=email, name=name, role=role, password_hash=hash_password(password)))
        print('User created.')
