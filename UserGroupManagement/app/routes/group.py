from fastapi import APIRouter, Depends, HTTPException, Query
from app.models import GroupCreate, MemberAdd
from typing import Optional, List
from app.services import create_group, add_member
from app.utils import get_current_user

router = APIRouter()

@router.get("/auth/introspect", summary="Return the JWT payload for debugging", tags=["Auth"])
def introspect(user=Depends(get_current_user)):
    # Helps verify the token/secret are aligned across services
    return {"user": user}

# Endpoint to create a new group
@router.post("/groups", summary="Create a group", tags=["Groups"])
def create_group_endpoint(group: GroupCreate, user=Depends(get_current_user)):
    return create_group(group, created_by=user["sub"])


# Endpoint to add a member to a group
@router.post("/group/add-member", summary="Add member to a group", tags=["Members"])
def add_member_endpoint(member: MemberAdd, user=Depends(get_current_user)):
    # Only the group owner can add members
    from app.authz_utils import ensure_owner_or_403
    ensure_owner_or_403(user["sub"], member.group_id)
    return add_member(member)



from app.utils import supabase
from app.email_utils import send_email
import datetime
from app.authz_utils import ensure_owner_or_403
from app.authz_utils import ensure_member_or_403
import uuid

# Internal helpers to avoid duplicate code
def _enrich_members(members):
    """Augment group_members rows with user first/last/email. Keeps fields minimal."""
    if not members:
        return []
    user_ids = list({m["user_id"] for m in members})
    users_res = supabase.table("users").select("id, first_name, last_name, email").in_("id", user_ids).execute()
    names_map = {u["id"]: {
        "first_name": u.get("first_name", ""),
        "last_name": u.get("last_name", ""),
        "email": u.get("email", "")
    } for u in (users_res.data or [])}
    enriched = []
    for m in members:
        info = names_map.get(m["user_id"], {})
        enriched.append({
            "group_id": m.get("group_id"),
            "user_id": m["user_id"],
            "first_name": info.get("first_name", ""),
            "last_name": info.get("last_name", ""),
            "email": info.get("email", ""),
            "phone_number": m.get("phone_number", ""),
            "relationship_tag": m.get("relationship_tag", "")
        })
    return enriched
# Update group details
@router.put("/groups/{group_id}", summary="Update group details", tags=["Groups"])
# Endpoint to update group details
def update_group(group_id: str, name: Optional[str] = None, description: Optional[str] = None, user=Depends(get_current_user)):
    # Only owner can update
    ensure_owner_or_403(user["sub"], group_id)
    update_data = {}
    if name:
        update_data["name"] = name
    if description:
        update_data["description"] = description
    response = supabase.table("groups").update(update_data).eq("id", group_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to update group")
    return {"msg": "Group updated successfully"}

# Delete group
@router.delete("/groups/{group_id}", summary="Delete a group", tags=["Groups"])
def delete_group(group_id: str, user=Depends(get_current_user)):
    # Only owner can delete
    ensure_owner_or_403(user["sub"], group_id)
    # Cascade delete group members
    supabase.table("group_members").delete().eq("group_id", group_id).execute()
    response = supabase.table("groups").delete().eq("id", group_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to delete group")
    return {"msg": "Group deleted successfully"}

# Invite member by email (stub)
@router.post("/groups/{group_id}/invites", summary="Send group invite via email", tags=["Invites"])
def invite_member(group_id: str, email: Optional[str] = None, phone: Optional[str] = None, user=Depends(get_current_user)):
    # Only owner can invite
    ensure_owner_or_403(user["sub"], group_id)
    errors = []
    group_name = group_id
    try:
        from app.utils import get_supabase_client
        supabase = get_supabase_client()
        res = supabase.table("groups").select("name").eq("id", group_id).execute()
        if res.data and len(res.data) > 0:
            group_name = res.data[0]["name"]
    except Exception as e:
        errors.append(f"Group name fetch error: {e}")
    if email:
        subject = "SplitBuddy Group Invitation"
        body = f"Hi,\n\nYou have been invited to join group '{group_name}' on SplitBuddy.\n\nPlease accept the invitation in the app.\n\nThank you!"
        try:
            send_email(email, subject, body)
            # Best-effort: persist invite if a table exists
            try:
                from app.utils import get_supabase_client
                supabase = get_supabase_client()
                # Idempotent upsert based on (group_id, invited_email)
                existing = supabase.table("group_invites").select("id, status").eq("group_id", group_id).eq("invited_email", email).execute()
                now_iso = datetime.datetime.utcnow().isoformat()
                if existing.data:
                    supabase.table("group_invites").update({
                        "status": "pending",
                        "invited_by": user["sub"],
                        "updated_at": now_iso,
                    }).eq("id", existing.data[0]["id"]).execute()
                else:
                    supabase.table("group_invites").insert({
                        "id": str(uuid.uuid4()),
                        "group_id": group_id,
                        "invited_email": email,
                        "invited_by": user["sub"],
                        "status": "pending",
                        "created_at": now_iso,
                    }).execute()
            except Exception:
                # Table might not exist; ignore
                pass
        except Exception as e:
            errors.append(f"Email error: {e}")
    # SMS is not supported in this project
    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))
    return {"msg": f"Invitation sent to {email or phone} for group {group_name}"}

# Accept/Reject group invitation (stub)

# Updated endpoint: require phone_number and relationship_tag when accepting invitation
@router.post("/groups/{group_id}/invitations/respond", summary="Accept or reject a group invitation", tags=["Invites"])
def respond_invitation(group_id: str, accept: bool, phone_number: str = None, relationship_tag: str = None, user=Depends(get_current_user)):
    # If invitation is accepted, require phone_number and relationship_tag
    if accept:
        if not phone_number or not relationship_tag:
            raise HTTPException(status_code=400, detail="phone_number and relationship_tag are required to join the group")
        from app.utils import get_supabase_client
        supabase = get_supabase_client()
        try:
            # Idempotent: if already a member, return success
            exists = supabase.table("group_members").select("user_id").eq("group_id", group_id).eq("user_id", user["sub"]).execute()
            if exists.data:
                return {"msg": f"Already a member of group {group_id}"}
            supabase.table("group_members").insert({
                "group_id": group_id,
                "user_id": user["sub"],
                "phone_number": phone_number,
                "relationship_tag": relationship_tag
            }).execute()
        except Exception as e:
            return {"msg": f"Failed to add user to group: {e}"}
        # Best-effort: mark invite accepted based on user's email
        try:
            # Find user's email and update any matching pending invites
            me = supabase.table("users").select("email").eq("id", user["sub"]).execute()
            user_email = (me.data[0]["email"] if me and me.data else None)
            if user_email:
                supabase.table("group_invites").update({"status": "accepted", "updated_at": datetime.datetime.utcnow().isoformat()}).eq("group_id", group_id).eq("invited_email", user_email).execute()
        except Exception:
            pass
        return {"msg": f"Invitation accepted and user added to group {group_id}"}
    # If invitation is rejected, do nothing
    try:
        # Best-effort: mark invite rejected
        me = supabase.table("users").select("email").eq("id", user["sub"]).execute()
        user_email = (me.data[0]["email"] if me and me.data else None)
        if user_email:
            supabase.table("group_invites").update({"status": "rejected", "updated_at": datetime.datetime.utcnow().isoformat()}).eq("group_id", group_id).eq("invited_email", user_email).execute()
    except Exception:
        pass
    return {"msg": f"Invitation rejected for group {group_id}"}

# List invites (persisted) for a group
@router.get("/groups/{group_id}/invites", summary="List invites for a group", tags=["Invites"])
def list_group_invites(group_id: str, status: Optional[str] = Query(None), user=Depends(get_current_user)):
    # Only owner can view pending/accepted invites
    ensure_owner_or_403(user["sub"], group_id)
    try:
        from app.utils import get_supabase_client
        supabase = get_supabase_client()
        q = supabase.table("group_invites").select("id, group_id, invited_email, invited_by, status, created_at, updated_at").eq("group_id", group_id)
        if status:
            q = q.eq("status", status)
        res = q.order("created_at", desc=True).execute()
        return {"invites": res.data or []}
    except Exception:
        # Table might not exist; return empty list with a hint
        return {"invites": [], "note": "No invite store found. Create a 'group_invites' table to persist invites."}

# List all groups a user belongs to
@router.get("/groups/mine", summary="List groups I belong to", tags=["Groups"])
def user_groups(user=Depends(get_current_user)):
    response = supabase.table("group_members").select("group_id").eq("user_id", user["sub"]).execute()
    group_ids = [g["group_id"] for g in response.data] if response.data else []
    groups = []
    if group_ids:
        groups_resp = supabase.table("groups").select("id", "name", "description").in_("id", group_ids).execute()
        groups = groups_resp.data if groups_resp.data else []
    return {"groups": groups}

# Audit log / activity history (stub)
@router.get("/groups/{group_id}/audit-log", summary="Get group activity log", tags=["Groups"])
def audit_log(group_id: str, user=Depends(get_current_user)):
    # Members only
    ensure_member_or_403(user["sub"], group_id)
    # TODO: Implement audit log table and query
    return {"log": ["Member added", "Relationship tagged", "Group updated"]}


# Group admins/roles: update relationship_tag in group_members table


@router.post("/groups/{group_id}/members/{user_id}/role", summary="Set a member's role/relationship tag", tags=["Members"])
def set_role(group_id: str, user_id: str, role: str, user=Depends(get_current_user)):
    from app.utils import get_supabase_client
    supabase = get_supabase_client()
    # Authorization: only group owner can set roles
    ensure_owner_or_403(user["sub"], group_id)
    # Debug: fetch all group_members for this group
    all_members = supabase.table("group_members").select("user_id", "group_id", "phone_number", "relationship_tag").eq("group_id", group_id).execute()
    # Check if user is a member of the group
    member_check = supabase.table("group_members").select("user_id").eq("group_id", group_id).eq("user_id", user_id).execute()
    if not member_check.data:
        raise HTTPException(status_code=404, detail={
            "error": f"User {user_id} is not a member of group {group_id}. Add the user to the group first.",
            "group_members": all_members.data
        })
    # Update role
    response = supabase.table("group_members").update({"relationship_tag": role}).eq("group_id", group_id).eq("user_id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail={
            "error": "Failed to set role. User is a member but update failed.",
            "group_members": all_members.data
        })
    return {"msg": f"Set role {role} for user {user_id} in group {group_id}"}

# Membership-scoped search: list my groups, filter by group/name, and optionally find members by name
@router.get("/groups/search", summary="Search my groups and members", tags=["Groups"])
def search_groups_members(
    group_name: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    member_name: Optional[str] = Query(None),
    skip_groups: int = Query(0, ge=0),
    limit_groups: int = Query(20, ge=1, le=100),
    skip_members: int = Query(0, ge=0),
    limit_members: int = Query(20, ge=1, le=100),
    include_counts: bool = Query(False),
    user=Depends(get_current_user)
):
    # 1) Determine all groups the user belongs to
    gm_res = supabase.table("group_members").select("group_id").eq("user_id", user["sub"]).execute()
    my_group_ids = list({row["group_id"] for row in (gm_res.data or [])})
    if not my_group_ids:
        return {"groups": [], "members": [], "groups_total": 0, "members_total": 0} if include_counts else {"groups": [], "members": []}

    # 2) Optionally narrow to a specific group_id (must be in my memberships)
    selected_ids = my_group_ids
    if group_id:
        if group_id in my_group_ids:
            selected_ids = [group_id]
        else:
            return {"groups": [], "members": []}

    # 3) Fetch groups, optionally filter by name (fetch all for counts; then page)
    g_query = supabase.table("groups").select("id", "name", "description").in_("id", selected_ids)
    if group_name:
        # Exact, case-insensitive match using ILIKE without wildcards
        g_query = g_query.ilike("name", group_name)
    all_groups_resp = g_query.execute()
    all_groups = all_groups_resp.data or []
    groups_total = len(all_groups)
    groups = all_groups[skip_groups: skip_groups + limit_groups]

    # 4) If member_name provided, fetch members of the selected groups and filter by name
    members_out = []
    members_total = 0
    if member_name and groups:
        group_ids_to_search = [g["id"] for g in groups]
        m_resp = supabase.table("group_members").select("group_id, user_id, phone_number, relationship_tag").in_("group_id", group_ids_to_search).execute()
        enriched = _enrich_members(m_resp.data or [])
        q = member_name.lower()
        filtered = [m for m in enriched if q in (m.get("first_name", "").lower()) or q in (m.get("last_name", "").lower())]
        members_total = len(filtered)
        members_out = filtered[skip_members: skip_members + limit_members]

    result = {"groups": groups, "members": members_out}
    if include_counts:
        result.update({"groups_total": groups_total, "members_total": members_total})
    return result

# Pagination & filtering for group list
@router.get("/group/list-paged", summary="List my groups (paged)", tags=["Groups"])
def list_groups_paged(user=Depends(get_current_user), skip: int = Query(0), limit: int = Query(10)):
    # Return paged groups the user is a member of
    gm = supabase.table("group_members").select("group_id").eq("user_id", user["sub"]).execute()
    group_ids = [g["group_id"] for g in (gm.data or [])]
    if not group_ids:
        return {"groups": []}
    g_resp = supabase.table("groups").select("id", "name", "description").in_("id", group_ids).execute()
    all_groups = g_resp.data or []
    groups = all_groups[skip: skip + limit]
    return {"groups": groups}



# Notifications (real email and SMS)
@router.post("/groups/{group_id}/notify/{user_id}", summary="Notify a user in a group", tags=["Notifications"])
def notify_user(group_id: str, user_id: str, message: str, email: str = None, phone: str = None, user=Depends(get_current_user)):
    # Only owner can notify users in group (adjust policy if needed)
    ensure_owner_or_403(user["sub"], group_id)
    # Ensure target user is a member of the group
    m_check = supabase.table("group_members").select("user_id").eq("group_id", group_id).eq("user_id", user_id).execute()
    if not m_check.data:
        raise HTTPException(status_code=404, detail=f"Target user {user_id} is not a member of group {group_id}")
    errors = []
    if email:
        try:
            send_email(email, "Group Notification", message)
        except Exception as e:
            errors.append(f"Email error: {e}")
    # SMS delivery disabled (Twilio removed)
    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))
    return {"msg": f"Notification sent to user {user_id} in group {group_id}: {message}"}

@router.get("/group/list", summary="List all groups I belong to", tags=["Groups"])
def list_groups(user=Depends(get_current_user)):
    # Return all groups the current user is a member of (not just created)
    gm = supabase.table("group_members").select("group_id").eq("user_id", user["sub"]).execute()
    group_ids = [g["group_id"] for g in (gm.data or [])]
    if not group_ids:
        return {"groups": []}
    groups_resp = supabase.table("groups").select("id", "name", "description").in_("id", group_ids).execute()
    return {"groups": groups_resp.data or []}


# List members of a group
@router.get("/groups/{group_id}/members", summary="List members of a group", tags=["Members"])
def list_members(group_id: str, user=Depends(get_current_user)):
    # Only members can list members
    ensure_member_or_403(user["sub"], group_id)
    response = supabase.table("group_members").select("group_id, user_id, phone_number, relationship_tag").eq("group_id", group_id).execute()
    enriched = _enrich_members(response.data or [])
    # Remove group_id in this endpoint to keep response same as before
    for m in enriched:
        m.pop("group_id", None)
    return {"members": enriched}


# Tag relationship for a member
@router.post("/groups/{group_id}/members/{user_id}/relationship-tag", summary="Tag a member's relationship", tags=["Members"])
def tag_relationship(group_id: str, user_id: str, relationship_tag: str, user=Depends(get_current_user)):
    # Only owner can tag relationships
    ensure_owner_or_403(user["sub"], group_id)
    response = supabase.table("group_members").update({"relationship_tag": relationship_tag}).eq("group_id", group_id).eq("user_id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to tag relationship")
    return {"msg": f"Tagged user {user_id} as {relationship_tag} in group {group_id}"}


# Remove member from a group
@router.delete("/groups/{group_id}/members/{user_id}", summary="Remove member from a group", tags=["Members"])
def remove_member(group_id: str, user_id: str, user=Depends(get_current_user)):
    # Only owner can remove members
    ensure_owner_or_403(user["sub"], group_id)
    response = supabase.table("group_members").delete().eq("group_id", group_id).eq("user_id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to remove member")
    return {"msg": f"Removed user {user_id} from group {group_id}"}
