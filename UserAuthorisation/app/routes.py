"""Authorization service routes.

These endpoints validate JWTs and make simple authorization decisions
against data stored in Supabase (groups, members, expenses).

They are designed to be called by other microservices.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils import get_supabase_client
import os, jwt

router = APIRouter()
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "mysecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Decode and validate the bearer JWT.

    Returns the decoded claims as a dict. Raises 401 on invalid/expired token.
    """
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/auth/introspect", summary="Validate JWT and return claims", tags=["AuthZ"])
def introspect(user=Depends(get_current_user)):
    """Return a basic token introspection response.

    Useful for quickly checking the caller's identity and email.
    """
    return {"active": True, "sub": user.get("sub"), "email": user.get("email")}

@router.get("/authz/groups/{group_id}/is-member", summary="Check if current user is a member of group", tags=["AuthZ"]) 
def is_member(group_id: str, user=Depends(get_current_user)):
    """Return whether the current user is a member of the given group."""
    supabase = get_supabase_client()
    res = supabase.table("group_members").select("user_id").eq("group_id", group_id).eq("user_id", user["sub"]).execute()
    return {"is_member": bool(res.data)}

@router.get("/authz/groups/{group_id}/is-owner", summary="Check if current user owns the group", tags=["AuthZ"]) 
def is_owner(group_id: str, user=Depends(get_current_user)):
    """Return whether the current user is the owner (created_by) of the group."""
    supabase = get_supabase_client()
    res = supabase.table("groups").select("created_by").eq("id", group_id).execute()
    if not res.data:
        return {"is_owner": False}
    return {"is_owner": res.data[0].get("created_by") == user["sub"]}

@router.get("/authz/expenses/{expense_id}/in-group", summary="Check if current user is in group of an expense", tags=["AuthZ"]) 
def expense_in_group(expense_id: str, user=Depends(get_current_user)):
    """Return whether the current user is a member of the group that owns the expense."""
    supabase = get_supabase_client()
    exp = supabase.table("expenses").select("group_id").eq("id", expense_id).execute()
    if not exp.data:
        return {"in_group": False}
    gid = exp.data[0]["group_id"]
    mem = supabase.table("group_members").select("user_id").eq("group_id", gid).eq("user_id", user["sub"]).execute()
    return {"in_group": bool(mem.data)}

# The POST /authz/decision endpoint has been removed to keep this service read-only.


