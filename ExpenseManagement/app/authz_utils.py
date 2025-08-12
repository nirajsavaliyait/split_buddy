"""Authorization helpers for the Expense service.

Provide membership checks and expense->group resolution using local
Supabase queries only (no cross-service delegation).
"""

from fastapi import HTTPException
from app.utils import get_supabase_client
import os

def is_member(user_id: str, group_id: str) -> bool:
    """Return True if the user belongs to the given group."""
    supabase = get_supabase_client()
    res = supabase.table("group_members").select("user_id").eq("group_id", group_id).eq("user_id", user_id).execute()
    return bool(res.data)

def get_expense_group(expense_id: str) -> str | None:
    """Return the group_id owning the expense or None if not found."""
    supabase = get_supabase_client()
    exp = supabase.table("expenses").select("group_id").eq("id", expense_id).execute()
    if not exp.data:
        return None
    return exp.data[0]["group_id"]

def ensure_member_or_403(user_id: str, group_id: str):
    """Raise 403 if the user is not a member of the group."""
    if not is_member(user_id, group_id):
        raise HTTPException(status_code=403, detail="Not a member of this group")

def ensure_member_by_expense_or_403(user_id: str, expense_id: str):
    """Resolve the expense's group and raise 403 if user is not a member."""
    gid = get_expense_group(expense_id)
    if not gid:
        raise HTTPException(status_code=404, detail="Expense not found")
    ensure_member_or_403(user_id, gid)
