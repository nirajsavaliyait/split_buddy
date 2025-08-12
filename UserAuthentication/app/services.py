"""Business logic for the Authentication service.

Includes user creation, login, profile read/update, email verification,
password reset request/confirm. Uses Supabase as the data store.
"""

# This logic imports utilities and models
from app.utils import supabase, hash_password, verify_password
from app.models import UserCreate, UserLogin, EmailVerification, PasswordResetRequest, PasswordReset, UserProfileUpdate
from fastapi import HTTPException
import uuid
import datetime
import pytz
from dateutil.parser import parse as parse_datetime

## Create a new user and send verification email
def create_user(user: UserCreate):
    existing = supabase.table("users").select("id").eq("email", user.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(user.password)
    verification_token = str(uuid.uuid4())
    supabase.table("users").insert({
        "email": user.email,
        "password_hash": hashed,
        "is_verified": False,
        "verification_token": verification_token,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }).execute()
    # TODO: Send verification email with token
    return {"msg": "User created successfully. Please verify your email."}

## Authenticate user credentials and check verification
def authenticate_user(user: UserLogin):
    result = supabase.table("users").select("*").eq("email", user.email).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    user_data = result.data[0]
    if not verify_password(user.password, user_data["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    if not user_data.get("is_verified", False):
        raise HTTPException(status_code=403, detail="Email not verified")
    # TODO: Detect new device/IP and send notification
    return user_data

## Fetch user profile (selected fields)
def get_user_profile(user_id: str):
    res = supabase.table("users").select("id, email, first_name, last_name, profile_picture, is_verified").eq("id", user_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")
    return res.data[0]

## Update user profile fields
def update_user_profile(user_id: str, payload: UserProfileUpdate):
    update_data = {}
    # Normalize helper: treat empty strings as "no change"
    def normalize(value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            # Treat empty strings and Swagger placeholders as no change
            if v == "":
                return None
            if v.lower() == "string":
                return None
            if v.lower() == "user@example.com":
                return None
        return value

    first_name = normalize(payload.first_name)
    last_name = normalize(payload.last_name)
    email = normalize(getattr(payload, "email", None))

    if first_name is not None:
        update_data["first_name"] = first_name
    if last_name is not None:
        update_data["last_name"] = last_name
    if email is not None:
        # Check if email is taken by another user
        exists = supabase.table("users").select("id").eq("email", email).neq("id", user_id).execute()
        if exists.data:
            raise HTTPException(status_code=400, detail="Email already registered")
        update_data["email"] = email
    if not update_data:
        return {"msg": "Nothing to update"}
    supabase.table("users").update(update_data).eq("id", user_id).execute()
    return {"msg": "Profile updated"}

## Verify user email using token
def verify_email(token: str):
    result = supabase.table("users").select("*").eq("verification_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    user_id = result.data[0]["id"]
    supabase.table("users").update({"is_verified": True, "verification_token": None}).eq("id", user_id).execute()
    return {"msg": "Email verified successfully"}

# This logic handles password reset request
def request_password_reset(email: str):
    result = supabase.table("users").select("id").eq("email", email).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Email not found")
    reset_token = str(uuid.uuid4())
    expiry = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
    supabase.table("users").update({"reset_token": reset_token, "reset_token_expiry": expiry}).eq("email", email).execute()
    # TODO: Send password reset email with token
    return {"msg": "Password reset email sent",
             "token": reset_token 
             }

# This logic resets the password using token
def reset_password(token: str, new_password: str):
    try:
        print(f"reset_password called with token={token}, new_password={new_password}")
        result = supabase.table("users").select("id", "reset_token_expiry").eq("reset_token", token).execute()
        print(f"Supabase result: {result}")
        if not result.data:
            print("No user found for token")
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        expiry = result.data[0]["reset_token_expiry"]
        print(f"Expiry value: {expiry}")
        from dateutil.parser import parse as parse_datetime
        if expiry:
            try:
                expiry_dt = parse_datetime(expiry)
                print(f"Parsed expiry datetime: {expiry_dt}")
                utc_now = datetime.datetime.now(pytz.UTC)
                if expiry_dt < utc_now:
                    print("Token expired")
                    raise HTTPException(status_code=400, detail="Token expired")
            except Exception as e:
                print(f"Error parsing expiry: {e}")
                raise HTTPException(status_code=500, detail=f"Error parsing expiry: {e}")
        user_id = result.data[0]["id"]
        hashed = hash_password(new_password)
        supabase.table("users").update({"password_hash": hashed, "reset_token": None, "reset_token_expiry": None}).eq("id", user_id).execute()
        print("Password reset successful")
        return {"msg": "Password reset successful"}
    except Exception as e:
        print("Exception in reset_password:", e)
        raise

