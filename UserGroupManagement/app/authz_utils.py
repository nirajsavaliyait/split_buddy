"""Authorization helpers for the Group service.

Centralize membership/ownership checks and raise HTTP 403 when the caller
is not allowed to perform an action. This version uses only local checks
against Supabase (no cross-service delegation).
"""

from fastapi import HTTPException
from app.utils import supabase
import os

def is_member(user_id: str, group_id: str) -> bool:
    """Return True if the user belongs to the given group."""
    res = supabase.table("group_members").select("user_id").eq("group_id", group_id).eq("user_id", user_id).execute()
    return bool(res.data)

def is_owner(user_id: str, group_id: str) -> bool:
    """Return True if the user is the group's creator (owner)."""
    res = supabase.table("groups").select("created_by").eq("id", group_id).execute()
    return bool(res.data and res.data[0].get("created_by") == user_id)

def ensure_member_or_403(user_id: str, group_id: str):
    """Raise 403 if the user is not a member of the group."""
    if not is_member(user_id, group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")

def ensure_owner_or_403(user_id: str, group_id: str):
    """Raise 403 if the user is not the owner of the group."""
    if not is_owner(user_id, group_id):
        raise HTTPException(status_code=403, detail="Only group owner can perform this action")
