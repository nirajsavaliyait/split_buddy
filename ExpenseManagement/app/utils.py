import os
import jwt
from supabase import create_client
from dotenv import load_dotenv
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# Load environment variables from the .env file in the project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


_supabase = None

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

# JWT auth dependency for this service
JWT_SECRET = os.getenv("JWT_SECRET", "mysecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        payload = dict(payload)
        payload["token"] = credentials.credentials
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
