from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form, Body
from app.models import (
    UserCreate,
    UserLogin,
    PasswordResetRequest,
    PasswordReset,
    UserProfileUpdate,
)
from app.services import (
    create_user,
    authenticate_user,
    verify_email,
    request_password_reset,
    reset_password,
    get_user_profile,
    update_user_profile,
)
from app.utils import supabase, supabase_admin
from app.email_utils import send_email
from app.config import JWT_SECRET, REFRESH_TOKEN_SECRET, PROFILE_PIC_BUCKET, SUPABASE_URL, FRONTEND_RESET_URL, FRONTEND_VERIFY_URL
import jwt
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
import base64
import io
import uuid
# Defer heavy imports to runtime to avoid startup crashes in minimal images
# from PIL import Image, ExifTags
import json
from pydantic import BaseModel

router = APIRouter()
security = HTTPBearer()

@router.post("/signup", summary="Register a new user", tags=["Auth"])
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
    # Prefer a frontend verification URL if provided
    if token:
        if FRONTEND_VERIFY_URL:
            verify_link = f"{FRONTEND_VERIFY_URL}?token={token}"
            send_email(user.email, "Verify your email", f"Click this link to verify your email: {verify_link}")
        else:
            send_email(user.email, "Verify your email", f"Use this code to verify in the app: {token}")
    else:
        send_email(user.email, "Verify your email", "Verification token not found. Please try again.")
    return result

@router.post("/signin", summary="Sign in and get access/refresh tokens", tags=["Auth"])
def signin(user: UserLogin):
    user_data = authenticate_user(user)
    access_token = jwt.encode(
        {"sub": user_data["id"], "email": user_data["email"], "exp": datetime.utcnow() + timedelta(minutes=30)},
        JWT_SECRET,
        algorithm="HS256"
    )
    refresh_token = jwt.encode(
        {"sub": user_data["id"], "type": "refresh", "exp": datetime.utcnow() + timedelta(days=7)},
        REFRESH_TOKEN_SECRET,
        algorithm="HS256"
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


# ---- Google OAuth (skeleton; wire actual OAuth flow on frontend) ----
@router.get("/auth/google/login", summary="Start Google OAuth (frontend handles)", tags=["Auth"])
def google_login_start():
    """Return a hint/URL for frontend to initiate Google OAuth.
    In Expo/web, use Google SDK to get id_token and POST to /auth/google/callback.
    """
    return {"msg": "Use Google Sign-In on client to obtain id_token and POST to /auth/google/callback"}


class GoogleCallbackBody(BaseModel):
    id_token: str


@router.post("/auth/google/callback", summary="Exchange Google id_token for app tokens", tags=["Auth"])
def google_callback(body: GoogleCallbackBody):
    """Verify Google id_token (server-side), create/find user, and return JWTs.
    Note: Implement token verification using google-auth library in production.
    """
    id_token_val = body.id_token
    if not id_token_val:
        raise HTTPException(status_code=400, detail="id_token required")
    # TODO: Verify id_token with google.oauth2.id_token.verify_oauth2_token
    # For now, accept payload with email and sub parsed on client; mock user
    # Expect frontend to provide email in body for this placeholder
    email = None
    try:
        payload = json.loads(id_token_val)
        email = payload.get("email")
        google_sub = payload.get("sub")
    except Exception:
        # Not JSON; reject in placeholder
        raise HTTPException(status_code=400, detail="Invalid id_token placeholder")
    if not email:
        raise HTTPException(status_code=400, detail="email missing in id_token placeholder")
    # Upsert user by email
    try:
        existing = supabase.table("users").select("id, is_verified").eq("email", email).execute()
        if existing.data:
            user_id = existing.data[0]["id"]
        else:
            user_id = str(uuid.uuid4())
            supabase.table("users").insert({
                "id": user_id,
                "email": email,
                "is_verified": True,
                "password_hash": None,
                "first_name": "",
                "last_name": "",
            }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upsert user: {e}")
    access_token = jwt.encode(
        {"sub": user_id, "email": email, "exp": datetime.utcnow() + timedelta(minutes=60)},
        JWT_SECRET,
        algorithm="HS256"
    )
    refresh_token = jwt.encode(
        {"sub": user_id, "type": "refresh", "exp": datetime.utcnow() + timedelta(days=7)},
        REFRESH_TOKEN_SECRET,
        algorithm="HS256"
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/token/refresh", summary="Exchange refresh token for new access token", tags=["Auth"])
async def refresh_token_endpoint(request: Request):
    body = None
    try:
        body = await request.json()
    except Exception:
        pass
    token = (body or {}).get("refresh_token") if isinstance(body, dict) else None
    if not token:
        raise HTTPException(status_code=400, detail="refresh_token required")
    try:
        payload = jwt.decode(token, REFRESH_TOKEN_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")
        # issue new access token only
        access_token = jwt.encode(
            {"sub": payload["sub"], "exp": datetime.utcnow() + timedelta(minutes=60)},
            JWT_SECRET,
            algorithm="HS256"
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# This endpoint verifies email
@router.get("/verify-email", summary="Verify email via token", tags=["Auth"])
def verify_email_endpoint(token: str):
    return verify_email(token)

# This endpoint requests password reset
@router.post("/forgot-password", summary="Request password reset", tags=["Auth"])
def forgot_password(request: PasswordResetRequest):
    result = request_password_reset(request.email)
    reset_token = result["token"]
    # Prefer linking to the frontend's reset page if configured; otherwise include the token.
    reset_link = None
    if FRONTEND_RESET_URL:
        reset_link = f"{FRONTEND_RESET_URL}?token={reset_token}"
    email_body = (
        f"Hi,\n\nWe received a request to reset your password.\n"
        + (f"Click the link to reset: {reset_link}\n\n" if reset_link else f"Use this code in the app to reset: {reset_token}\n\n")
        + "If you didn’t request this, please ignore this email.\n\nThanks!"
    )

    send_email(request.email, "Password Reset", email_body)
    return {"msg": "Password reset email sent"}

# This endpoint resets password
@router.post("/reset-password", summary="Reset password with token", tags=["Auth"])
def reset_password_endpoint(reset: PasswordReset):
    return reset_password(reset.token, reset.new_password)

## Removed HTML reset form endpoint; frontend will provide the UI


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Removed private test route per architecture cleanup

# New, clearer endpoints
@router.get("/users/me", summary="Get my profile", tags=["Profile"])
def get_my_profile(user=Depends(get_current_user)):
    return get_user_profile(user["sub"])

@router.put("/users/me", summary="Update my profile", tags=["Profile"])
def update_my_profile(
    payload: UserProfileUpdate = Body(
        ...,
        examples={
            "update_only_first_name": {
                "summary": "Change first name only",
                "value": {"first_name": "New Name"}
            },
            "update_email": {
                "summary": "Change email",
                "value": {"email": "new@example.com"}
            },
            "empty": {
                "summary": "Leave empty to keep everything",
                "value": {}
            }
        }
    ),
    user=Depends(get_current_user)
):
    # Route-level sanitize: treat placeholders/empty strings as no change
    def sanitize(v: str | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if s == "" or s.lower() == "string" or s.lower() == "user@example.com":
                return None
        return v
    payload = UserProfileUpdate(
        first_name=sanitize(payload.first_name),
        last_name=sanitize(payload.last_name),
        email=sanitize(getattr(payload, "email", None))
    )
    return update_user_profile(user["sub"], payload)

 

# Upload or capture profile picture
# - Option 1: multipart/form-data with file field 'file'
# - Option 2: JSON with { "image_base64": "data:image/png;base64,..." } or raw base64 via form field 'image_base64'
@router.post("/users/me/profile-picture", summary="Upload or capture profile picture", tags=["Profile"])
async def upload_profile_picture(
    request: Request,
    file: UploadFile | None = File(default=None),
    image_base64: str | None = Form(default=None),
    user=Depends(get_current_user)
):
    # Import Pillow lazily to avoid import-time failures breaking app startup
    try:
        from PIL import Image, ExifTags  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing unavailable: {e}")
    user_id = user["sub"]
    content: bytes | None = None
    ext = "png"

    # Case 1: multipart file upload (from system)
    if file is not None:
        content = await file.read()
        # Infer extension from filename or content type
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
        elif file.content_type:
            if "/" in file.content_type:
                ext = file.content_type.split("/")[-1].lower()

    # Case 2: base64 (from camera capture)
    if content is None and image_base64:
        b64 = image_base64
        # Support data URL like 'data:image/png;base64,xxxx'
        if "," in b64:
            header, b64 = b64.split(",", 1)
            if "image/" in header and ";base64" in header:
                try:
                    ext = header.split("image/")[-1].split(";")[0]
                except Exception:
                    pass
        try:
            content = base64.b64decode(b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Case 2b: JSON body base64
    if content is None:
        try:
            body = await request.json()
            b64 = body.get("image_base64") if isinstance(body, dict) else None
            if b64:
                if "," in b64:
                    header, b64 = b64.split(",", 1)
                    if "image/" in header and ";base64" in header:
                        try:
                            ext = header.split("image/")[-1].split(";")[0]
                        except Exception:
                            pass
                content = base64.b64decode(b64)
        except Exception:
            # No JSON or invalid; ignore
            pass

    if content is None:
        raise HTTPException(status_code=400, detail="Provide a file or image_base64")

    # Only allow JPG or PNG; try to normalize/verify by magic bytes
    def sniff_ext(data: bytes) -> str | None:
        try:
            if data.startswith(b"\x89PNG\r\n\x1a\n"):
                return "png"
            if data.startswith(b"\xFF\xD8"):
                return "jpg"
        except Exception:
            return None
        return None

    sig_ext = sniff_ext(content)
    allowed = {"jpg", "jpeg", "png"}
    if sig_ext:
        ext = sig_ext  # prefer signature over filename/content-type
    if ext not in allowed:
        raise HTTPException(status_code=415, detail="Unsupported image type. Please upload a JPG or PNG.")
    # If signature exists and doesn't match allowed types, reject
    if sig_ext is None and ext in {"jpg", "jpeg", "png"}:
        # Could not verify signature; be strict and require valid image bytes
        raise HTTPException(status_code=400, detail="Invalid image data. Please upload a valid JPG or PNG.")

    # Validate size (e.g., <= 5MB)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 5MB)")

    # Process image: auto-rotate, strip EXIF, resize to a sensible max, and create thumbnail
    try:
        img = Image.open(io.BytesIO(content))
        # Auto-rotate based on EXIF Orientation
        try:
            exif = img._getexif()
            if exif:
                orientation_key = next(k for k, v in ExifTags.TAGS.items() if v == 'Orientation')
                orientation = exif.get(orientation_key)
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
        except Exception:
            pass
        # Convert to RGB for JPEG if needed
        if ext in ("jpg", "jpeg") and img.mode not in ("RGB",):
            img = img.convert("RGB")
        # Resize to max 1024x1024 preserving aspect ratio
        max_size = (1024, 1024)
        img.thumbnail(max_size)
        # Save processed main image to bytes
        main_bytes = io.BytesIO()
        save_format = "JPEG" if ext in ("jpg", "jpeg") else "PNG"
        save_kwargs = {"optimize": True}
        if save_format == "JPEG":
            save_kwargs.update({"quality": 85})
        img.save(main_bytes, format=save_format, **save_kwargs)
        main_bytes.seek(0)
        # Create thumbnail 128x128
        thumb = img.copy()
        thumb.thumbnail((128, 128))
        thumb_bytes = io.BytesIO()
        thumb.save(thumb_bytes, format=save_format, **save_kwargs)
        thumb_bytes.seek(0)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not process image. Please upload a valid JPG or PNG.")

    # Build paths and upload to Supabase Storage
    base_name = uuid.uuid4().hex
    filename = f"{user_id}/{base_name}.{ext}"
    thumbname = f"{user_id}/{base_name}_thumb.{ext}"
    try:
        storage_client = supabase_admin if supabase_admin is not None else supabase
        bucket = storage_client.storage.from_(PROFILE_PIC_BUCKET)
        # Best-effort cleanup of previously uploaded files in our bucket
        try:
            current = supabase.table("users").select("profile_picture").eq("id", user_id).execute()
            current_url = (current.data[0]["profile_picture"] if current and current.data else None)
            if current_url and isinstance(current_url, str):
                prefix = f"{SUPABASE_URL}/storage/v1/object/public/{PROFILE_PIC_BUCKET}/"
                if current_url.startswith(prefix):
                    old_path = current_url[len(prefix):]
                    # Derive thumbnail path if it follows the _thumb pattern
                    if "." in old_path:
                        base, ext_old = old_path.rsplit(".", 1)
                        old_thumb = f"{base}_thumb.{ext_old}"
                        try:
                            bucket.remove([old_path, old_thumb])
                        except Exception:
                            pass
        except Exception:
            pass
        # Map to canonical content types
        content_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        bucket.upload(filename, main_bytes.getvalue(), {"content_type": content_type})
        bucket.upload(thumbname, thumb_bytes.getvalue(), {"content_type": content_type})
        # Build a public URL
        public_url = bucket.get_public_url(filename)
        thumb_url = bucket.get_public_url(thumbname)
        # Persist URL to user profile
        supabase.table("users").update({"profile_picture": public_url}).eq("id", user_id).execute()
        return {"url": public_url, "thumbnail_url": thumb_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.delete("/users/me/profile-picture", summary="Remove current profile picture", tags=["Profile"])
def delete_profile_picture(user=Depends(get_current_user)):
    user_id = user["sub"]
    try:
        # Fetch current URL
        current = supabase.table("users").select("profile_picture").eq("id", user_id).execute()
        current_url = (current.data[0]["profile_picture"] if current and current.data else None)
        if not current_url:
            return {"msg": "No profile picture set"}

        storage_client = supabase_admin if supabase_admin is not None else supabase
        bucket = storage_client.storage.from_(PROFILE_PIC_BUCKET)
        # If the URL points to our public bucket, derive the storage path and thumbnail path
        prefix = f"{SUPABASE_URL}/storage/v1/object/public/{PROFILE_PIC_BUCKET}/"
        if isinstance(current_url, str) and current_url.startswith(prefix):
            old_path = current_url[len(prefix):]
            paths = [old_path]
            if "." in old_path:
                base, ext = old_path.rsplit(".", 1)
                paths.append(f"{base}_thumb.{ext}")
            try:
                bucket.remove(paths)
            except Exception:
                # Best-effort delete
                pass

        # Clear profile_picture in DB
        try:
            supabase.table("users").update({"profile_picture": None}).eq("id", user_id).execute()
        except Exception:
            supabase.table("users").update({"profile_picture": ""}).eq("id", user_id).execute()
        return {"msg": "Profile picture removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove profile picture: {e}")


@router.get("/users/me/profile-picture", summary="Get current profile picture and thumbnail", tags=["Profile"])
def get_profile_picture(user=Depends(get_current_user)):
    user_id = user["sub"]
    res = supabase.table("users").select("profile_picture").eq("id", user_id).execute()
    url = (res.data[0]["profile_picture"] if res and res.data else None)
    thumb_url = None
    if url and isinstance(url, str):
        prefix = f"{SUPABASE_URL}/storage/v1/object/public/{PROFILE_PIC_BUCKET}/"
        if url.startswith(prefix) and "." in url:
            base, ext = url.rsplit(".", 1)
            thumb_url = f"{base}_thumb.{ext}"
    return {"url": url, "thumbnail_url": thumb_url}

# (legacy /me routes removed)

# ----- User settings: reminders and theme -----
class UserSettings(BaseModel):
    reminder_frequency: str | None = None  # e.g., daily, weekly, monthly
    reminder_style: str | None = None      # e.g., meme, plain
    theme: str | None = None               # light | dark | system


@router.get("/users/me/settings", summary="Get my settings", tags=["Settings"])
def get_my_settings(user=Depends(get_current_user)):
    res = supabase.table("user_settings").select("reminder_frequency, reminder_style, theme").eq("user_id", user["sub"]).execute()
    if res.data:
        return res.data[0]
    return {"reminder_frequency": None, "reminder_style": None, "theme": None}


@router.put("/users/me/settings", summary="Update my settings", tags=["Settings"])
def update_my_settings(body: UserSettings, user=Depends(get_current_user)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    data["user_id"] = user["sub"]
    # Upsert-like behavior
    existing = supabase.table("user_settings").select("user_id").eq("user_id", user["sub"]).execute()
    if existing.data:
        supabase.table("user_settings").update(data).eq("user_id", user["sub"]).execute()
    else:
        supabase.table("user_settings").insert(data).execute()
    return {"msg": "Settings saved"}

# (Phone/OTP endpoints removed; email-only auth retained)
