from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
from passlib.context import CryptContext

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# Optional privileged client for Storage writes when RLS blocks anon key
supabase_admin: Client | None = None
try:
    if SUPABASE_SERVICE_KEY:
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
except Exception:
    supabase_admin = None
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

## Hash a password using bcrypt
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

## Verify a plain password against a hashed password
def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
