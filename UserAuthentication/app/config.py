import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
JWT_SECRET = os.getenv("JWT_SECRET", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFkbnV1b3loY3NsdXZleG9sbW9uIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NDM3Njk1MywiZXhwIjoyMDY5OTUyOTUzfQ._ALcDQEcl6vj_zGQ9G9UxF9I7xn0ZfBTtulqtelxZD8")
NGROK_URL = os.getenv("NGROK_URL")