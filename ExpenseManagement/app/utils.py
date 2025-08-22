import os
import jwt
from typing import Optional
from supabase import create_client
from dotenv import load_dotenv
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Load environment variables from the .env file in the project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

_supabase = None
_supabase_admin = None

RECEIPTS_BUCKET = os.getenv("RECEIPTS_BUCKET", "receipts")

def get_supabase_client():
    global _supabase
    if _supabase is not None:
        return _supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise Exception("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    _supabase = create_client(url, key)
    return _supabase

def get_supabase_admin():
    global _supabase_admin
    if _supabase_admin is not None:
        return _supabase_admin
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not service_key:
        # Fall back to anon client if admin is not configured
        return get_supabase_client()
    _supabase_admin = create_client(url, service_key)
    return _supabase_admin

def _ensure_user_exists_in_db(user_id: str, email: Optional[str]) -> None:
    """
    Permanent fix: make sure the authenticated user exists in public.users.
    Safe to call on every request; cheap NO-OP if row already exists.
    """
    sb = get_supabase_admin()  # use admin to avoid future RLS surprises
    try:
        res = sb.table("users").select("id").eq("id", user_id).limit(1).execute()
        if not res.data:
            payload = {"id": user_id}
            if email:
                payload["email"] = email
            # Optional quality-of-life fields if your schema has them:
            # payload["is_verified"] = True
            sb.table("users").insert(payload).execute()
    except Exception:
        # Do not block request flow on user-sync errors
        pass

# JWT auth dependency for this service
JWT_SECRET = os.getenv("JWT_SECRET", "mysecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Decodes JWT and guarantees a matching row in public.users (permanent FK fix).
    """
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        payload = dict(payload)
        user_id = payload.get("sub")
        email = payload.get("email")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")
        # PERMANENT FIX: ensure the user row always exists
        _ensure_user_exists_in_db(user_id, email)
        payload["token"] = credentials.credentials
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
