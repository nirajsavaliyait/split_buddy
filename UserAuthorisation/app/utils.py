import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables from this service's .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

_supabase = None

def get_supabase_client():
    global _supabase
    if _supabase is not None:
        return _supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise Exception("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    _supabase = create_client(supabase_url, supabase_key)
    return _supabase
