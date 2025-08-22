from app.models import GroupCreate, MemberAdd
from app.utils import get_supabase_client
from fastapi import HTTPException
import uuid
import re


def _digits10(phone: str) -> str:
    """Return 10-digit local number if possible; else ''."""
    digits = re.sub(r"[^0-9]", "", phone or "")
    if len(digits) == 10:
        return digits
    if len(digits) == 12 and digits.startswith("91"):
        return digits[-10:]
    return ""

def create_group(group: GroupCreate, created_by: str):
    # Create a new group in the database
    group_id = str(uuid.uuid4())
    supabase = get_supabase_client()
    # 1) Create the group row
    supabase.table("groups").insert({
        "id": group_id,
        "name": group.name,
        "description": group.description,
        "created_by": created_by
    }).execute()
    # 2) Ensure the creator is also a member of the group
    # This keeps authorization consistent (owner can access member-scoped endpoints)
    try:
        # Best-effort: fetch creator's phone from users table
        phone10 = None
        try:
            info = supabase.table("users").select("phone").eq("id", created_by).execute()
            if info.data:
                phone10 = _digits10(info.data[0].get("phone")) or None
        except Exception:
            pass
        member_row = {
            "group_id": group_id,
            "user_id": created_by,
            "relationship_tag": "owner"
        }
        if phone10:
            member_row["phone_number"] = phone10
        supabase.table("group_members").insert(member_row).execute()
    except Exception:
        # If a constraint prevents duplicates or table missing, ignore
        pass
    return {"group_id": group_id, "msg": "Group created successfully"}

def add_member(member: MemberAdd):
    # Add a new member to a group in the database
    supabase = get_supabase_client()
    supabase.table("group_members").insert({
        "group_id": member.group_id,
        "user_id": member.user_id,
        "phone_number": member.phone_number,
        "relationship_tag": member.relationship_tag
    }).execute()
    return {"msg": "Member added successfully"}

def list_groups_for_user(user_id: str):
    # List all groups for a given user (dummy implementation)
    return ["Trip to Goa", "Flatmates", "Office Lunch"]

def list_members_of_group(group_id: str):
    # List all members of a group (dummy implementation)
    return ["Alice", "Bob", "Charlie"]

def tag_relationship_in_group(group_id: str, user_id: str, relationship_tag: str):
    # Tag a relationship for a member in a group (dummy implementation)
    return True

def remove_member_from_group(group_id: str, user_id: str):
    # Remove a member from a group (dummy implementation)
    return True
