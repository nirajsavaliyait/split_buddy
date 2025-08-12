import os
import jwt
from supabase import create_client
from dotenv import load_dotenv
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# Load environment variables from the .env file in the project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


# Create and return a Supabase client using environment variables
def get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    ALGORITHM = os.getenv("ALGORITHM")
    if not supabase_url or not supabase_key:
        raise Exception("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(supabase_url, supabase_key)


# Create a global Supabase client instance for reuse across the service
supabase = get_supabase_client()

# JWT auth dependency (shared by route handlers)
JWT_SECRET = os.getenv("JWT_SECRET", "mysecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Decode and validate the bearer JWT for this service."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return dict(payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
