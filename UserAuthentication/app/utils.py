from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY
from passlib.context import CryptContext

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
