from fastapi import APIRouter, HTTPException, Depends, Request
from app.models import UserCreate, UserLogin, PasswordResetRequest, PasswordReset
from app.services import create_user, authenticate_user, verify_email, request_password_reset, reset_password
from app.utils import supabase
from app.email_utils import send_email
from app.config import JWT_SECRET, NGROK_URL
import jwt
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()
security = HTTPBearer()

@router.post("/signup")
# This endpoint registers a user and sends a verification email with a link
def signup(user: UserCreate):
    result = create_user(user)
    # Fetch verification token from DB
    user_record = None
    try:
        user_record = supabase.table("users").select("verification_token").eq("email", user.email).execute()
    except Exception as e:
        print(f"Error fetching verification token: {e}")
    token = user_record.data[0]["verification_token"] if user_record and user_record.data else None
    verify_link = f"{NGROK_URL}/verify-email?token={token}" if token else "Token not found"
    # Send verification email with link
    send_email(user.email, "Verify your email", f"Click this link to verify your email: {verify_link}")
    return result

@router.post("/signin")
def signin(user: UserLogin):
    user_data = authenticate_user(user)
    token = jwt.encode(
        {"sub": user_data["id"], "email": user_data["email"], "exp": datetime.utcnow() + timedelta(hours=1)},
        JWT_SECRET,
        algorithm="HS256"
    )
    return {"access_token": token, "token_type": "bearer"}

# This endpoint verifies email
@router.get("/verify-email")
def verify_email_endpoint(token: str):
    return verify_email(token)

# This endpoint requests password reset
@router.post("/forgot-password")
def forgot_password(request: PasswordResetRequest):
    result = request_password_reset(request.email)
    reset_token = result["token"]
    reset_link = f"{NGROK_URL}/reset-password-form?token={reset_token}"

    email_body = f"""
    Hi,

    We received a request to reset your password.
    Click the link below to reset it:

    {reset_link}

    If you didn’t request this, please ignore this email.

    Thanks!
    """

    send_email(request.email, "Password Reset", email_body)
    return {"msg": "Password reset email sent"}

# This endpoint resets password
@router.post("/reset-password")
def reset_password_endpoint(reset: PasswordReset):
    return reset_password(reset.token, reset.new_password)

@router.get("/reset-password-form", response_class=HTMLResponse)
def serve_reset_form(request: Request):
    return FileResponse("app/form/reset_password.html")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/private")
def private_route(user=Depends(get_current_user)):
    return {"msg": f"Hello, {user['email']}! This is a private route."}
