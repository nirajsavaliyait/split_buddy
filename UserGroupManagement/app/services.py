from app.models import GroupCreate, MemberAdd
from app.utils import get_supabase_client
from fastapi import HTTPException
import uuid

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
        supabase.table("group_members").insert({
            "group_id": group_id,
            "user_id": created_by,
            # Optional defaults; adjust if you want a specific owner tag
            "relationship_tag": "owner"
        }).execute()
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
