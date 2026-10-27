# app/gmail/config.py  (new file)
import os

def get_google_client(email: str) -> dict:
    domain = email.split("@")[-1].strip().lower()
    key = domain.split(".")[0].upper()   # izealinc -> IZEALINC, abdsinc -> ABDSINC
    client_id = os.getenv(f"GOOGLE_CLIENT_ID_{key}")
    client_secret = os.getenv(f"GOOGLE_CLIENT_SECRET_{key}")
    if not client_id or not client_secret:
        raise ValueError(f"No Google OAuth client configured for {domain}")
    return {"client_id": client_id, "client_secret": client_secret}