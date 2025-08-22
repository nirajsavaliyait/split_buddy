"""Expense service routes: beginner-friendly, robust, and well-commented.

Permanent fix included:
- get_current_user now auto-syncs the JWT user into public.users.
- We can safely insert created_by/paid_by on initial insert (FK will pass).
"""

from datetime import datetime
import io
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app.authz_utils import ensure_member_by_expense_or_403, ensure_member_or_403
from app.models import (
    ExpenseCreateRequest,
    ExpenseSplit,
    ExpenseUpdate,
    SplitCommitRequest,
    SplitPreviewRequest,
)
from app.utils import RECEIPTS_BUCKET, get_current_user, get_supabase_admin, get_supabase_client

router = APIRouter()

@router.post("/groups/{group_id}/expenses", summary="Create an expense in a group", tags=["Expenses"])
def create_expense(expense: ExpenseCreateRequest, group_id: Optional[str] = None, user=Depends(get_current_user)):
    """Create an expense with only two required fields in the body.

    With get_current_user now auto-syncing a row in public.users, we can safely set
    created_by/paid_by on insert. We still gracefully drop unknown columns and handle
    duplicate IDs.
    """
    expense_id = str(uuid.uuid4())
    gid = group_id
    if not gid:
        raise HTTPException(status_code=422, detail="group_id is required (path or body)")

    # Ensure caller is a member of the group
    ensure_member_or_403(user["sub"], gid)

    supabase = get_supabase_client()
    caller_id = user.get("sub")

    # Base data to insert; optional fields will be dropped if the DB doesn't have them
    data_full = {
        "id": expense_id,
        "group_id": gid,
        "description": expense.description,
        "amount": expense.amount,
        "created_by": caller_id,
        "paid_by": caller_id,
        "currency": "USD",
        "date": datetime.utcnow().isoformat(),
    }
    optional = ["currency", "date", "created_by", "paid_by"]
    dropped: set[str] = set()
    last_detail = None

    for _ in range(len(optional) + 3):
        data = {k: v for k, v in data_full.items() if k not in dropped}
        try:
            res = supabase.table("expenses").insert(data).execute()
            if not getattr(res, "error", None):
                return {"expense_id": data["id"], "msg": "Expense created successfully"}
            detail = getattr(res, "error", None) or getattr(res, "data", None) or "Unknown insert error"
        except Exception as e:
            detail = str(e)

        # Duplicate key
        as_text = str(detail)
        code = detail.get("code") if isinstance(detail, dict) else None
        if (code == "23505") or ("duplicate key" in as_text.lower()):
            data_full["id"] = str(uuid.uuid4())
            continue

        # NOT NULL violations: self-heal for known optional cols
        if (code == "23502") or ("null value in column" in as_text.lower()):
            mnn = re.search(r"null value in column\s+'?\"?([A-Za-z0-9_]+)\"?'?", as_text)
            col = mnn.group(1) if mnn else None
            if col == "date" and "date" not in dropped:
                data_full["date"] = datetime.utcnow().isoformat()
                last_detail = detail
                continue
            if col == "currency" and "currency" not in dropped:
                data_full["currency"] = "USD"
                last_detail = detail
                continue

        # Unknown/missing column → drop and retry
        missing = None
        m = re.search(r"Could not find the '([^']+)' column", as_text)
        if m:
            missing = m.group(1)
        else:
            m2 = re.search(r'column\s+"?([A-Za-z0-9_]+)"?\s+does not exist', as_text, re.IGNORECASE)
            if m2:
                missing = m2.group(1)
        if missing and missing in data_full and missing not in dropped:
            dropped.add(missing)
            last_detail = detail
            continue

        # Drop remaining optional fields sequentially
        for f in optional:
            if f not in dropped and f in data_full:
                dropped.add(f)
                last_detail = detail
                break
        else:
            last_detail = detail
            break

    raise HTTPException(status_code=500, detail=f"Failed to create expense: {last_detail}")

@router.get("/expenses/{expense_id}", summary="Get a single expense with splits", tags=["Expenses"])
def get_expense(expense_id: str, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    supabase = get_supabase_client()
    exp = supabase.table("expenses").select("*").eq("id", expense_id).execute()
    if not exp.data:
        raise HTTPException(status_code=404, detail="Expense not found")
    splits = supabase.table("expense_splits").select("user_id, amount, is_settled").eq("expense_id", expense_id).execute()
    return {"expense": exp.data[0], "splits": splits.data or []}

@router.patch("/expenses/{expense_id}", summary="Update an expense", tags=["Expenses"])
def update_expense(expense_id: str, payload: ExpenseUpdate, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not update:
        return {"msg": "No changes"}
    supabase = get_supabase_client()
    res = supabase.table("expenses").update(update).eq("id", expense_id).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Failed to update expense")
    return {"msg": "Expense updated"}

@router.delete("/expenses/{expense_id}", summary="Delete an expense", tags=["Expenses"])
def delete_expense(expense_id: str, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    supabase = get_supabase_client()
    res = supabase.table("expenses").delete().eq("id", expense_id).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Failed to delete expense")
    supabase.table("expense_splits").delete().eq("expense_id", expense_id).execute()
    return {"msg": "Expense deleted"}

@router.post("/expenses/{expense_id}/splits", summary="Add a split to an expense", tags=["Expenses"])
def split_expense(split: ExpenseSplit, expense_id: Optional[str] = None, user=Depends(get_current_user)):
    split_id = str(uuid.uuid4())
    eid = expense_id or getattr(split, "expense_id", None)
    if not eid:
        raise HTTPException(status_code=422, detail="expense_id is required (path or body)")
    ensure_member_by_expense_or_403(user["sub"], eid)
    data = {
        "id": split_id,
        "expense_id": eid,
        "user_id": split.user_id,
        "amount": split.amount,
        "is_settled": split.is_settled
    }
    supabase = get_supabase_client()
    res = supabase.table("expense_splits").insert(data).execute()
    if getattr(res, "error", None):
        raise HTTPException(status_code=500, detail=f"Failed to split expense: {getattr(res, 'error', None)}")
    return {"split_id": split_id, "msg": "Expense split added successfully"}

@router.get("/groups/{group_id}/expenses", summary="List expenses for a group", tags=["Expenses"])
def get_group_expenses(group_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       sort: Optional[str] = None, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    query = supabase.table("expenses").select("*").eq("group_id", group_id)
    start = (page - 1) * page_size
    end = start + page_size - 1
    if sort == "date_desc":
        query = query.order("date", desc=True)
    elif sort == "date_asc":
        query = query.order("date", desc=False)
    res = query.range(start, end).execute()
    return res.data

@router.get("/users/{user_id}/expenses", summary="List expenses for a user", tags=["Expenses"])
def get_user_expenses(user_id: str, user=Depends(get_current_user)):
    if user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    supabase = get_supabase_client()
    res = supabase.table("expense_splits").select("*").eq("user_id", user_id).execute()
    return res.data

@router.get("/expenses/{expense_id}/splits", summary="List splits for an expense", tags=["Splits"])
def list_splits(expense_id: str, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    supabase = get_supabase_client()
    res = supabase.table("expense_splits").select("user_id, amount, is_settled").eq("expense_id", expense_id).execute()
    return res.data or []

@router.get("/users/{user_id}/balances", summary="User net balance (optionally by group)", tags=["Balances"])
def user_balance(user_id: str, group_id: Optional[str] = Query(None), user=Depends(get_current_user)):
    if user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    supabase = get_supabase_client()
    if group_id:
        ensure_member_or_403(user_id, group_id)
        exps = supabase.table("expenses").select("id, amount").eq("group_id", group_id).eq("paid_by", user_id).execute().data or []
        paid_total = sum(float(e.get("amount", 0)) for e in exps)
        group_exps = supabase.table("expenses").select("id").eq("group_id", group_id).execute().data or []
        exp_ids = [e["id"] for e in group_exps]
        owed_total = 0.0
        if exp_ids:
            owed_rows = supabase.table("expense_splits").select("amount, expense_id").in_("expense_id", exp_ids).eq("user_id", user_id).execute().data or []
            owed_total = sum(float(r.get("amount", 0)) for r in owed_rows)
        balance = round(paid_total - owed_total, 2)
        return {"user_id": user_id, "group_id": group_id, "balance": balance}
    else:
        exps = supabase.table("expenses").select("amount").eq("paid_by", user_id).execute().data or []
        paid_total = sum(float(e.get("amount", 0)) for e in exps)
        owed_rows = supabase.table("expense_splits").select("amount").eq("user_id", user_id).execute().data or []
        owed_total = sum(float(r.get("amount", 0)) for r in owed_rows)
        return {"user_id": user_id, "balance": round(paid_total - owed_total, 2)}

@router.post("/expenses/{expense_id}/split/preview", summary="Preview split calculation", tags=["Splits"])
def preview_split(expense_id: str, body: SplitPreviewRequest, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    supabase = get_supabase_client()
    exp = supabase.table("expenses").select("amount").eq("id", expense_id).execute()
    if not exp.data:
        raise HTTPException(status_code=404, detail="Expense not found")
    total = body.amount or float(exp.data[0]["amount"])
    parts = body.participants
    if body.mode == "equal":
        n = len(parts)
        if n == 0:
            raise HTTPException(status_code=422, detail="No participants")
        share = round(total / n, 2)
        splits = [
            {"user_id": p.user_id, "amount": share if i < n - 1 else round(total - share * (n - 1), 2)}
            for i, p in enumerate(parts)
        ]
        return {"total": total, "splits": splits}
    elif body.mode == "percent":
        pct_sum = sum((p.percent or 0) for p in parts)
        if round(pct_sum, 4) != 100.0:
            raise HTTPException(status_code=422, detail="Percentages must sum to 100")
        splits = [{"user_id": p.user_id, "amount": round(total * (p.percent or 0) / 100.0, 2)} for p in parts]
        return {"total": total, "splits": splits}
    elif body.mode == "shares":
        total_shares = sum((p.shares or 0) for p in parts)
        if total_shares <= 0:
            raise HTTPException(status_code=422, detail="Total shares must be > 0")
        splits = [{"user_id": p.user_id, "amount": round(total * (p.shares or 0) / total_shares, 2)} for p in parts]
        return {"total": total, "splits": splits}
    elif body.mode == "exact":
        exact_sum = sum((p.exact_amount or 0) for p in parts)
        if round(exact_sum, 2) != round(total, 2):
            raise HTTPException(status_code=422, detail="Exact amounts must sum to total")
        splits = [{"user_id": p.user_id, "amount": round(p.exact_amount or 0, 2)} for p in parts]
        return {"total": total, "splits": splits}
    else:
        raise HTTPException(status_code=422, detail="Invalid mode")

@router.put("/expenses/{expense_id}/split", summary="Commit split items for an expense (overwrites)", tags=["Splits"])
def commit_split(expense_id: str, body: SplitCommitRequest, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    supabase = get_supabase_client()
    supabase.table("expense_splits").delete().eq("expense_id", expense_id).execute()
    to_insert = [
        {"id": str(uuid.uuid4()), "expense_id": expense_id, "user_id": s.user_id, "amount": s.amount, "is_settled": False}
        for s in body.splits
    ]
    if to_insert:
        res = supabase.table("expense_splits").insert(to_insert).execute()
        if getattr(res, "error", None):
            raise HTTPException(status_code=500, detail=f"Failed to commit splits: {getattr(res, 'error', None)}")
    return {"msg": "Splits committed", "count": len(to_insert)}

@router.get("/groups/{group_id}/balances", summary="Net balance per member in group", tags=["Balances"])
def group_balances(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    exps = supabase.table("expenses").select("id, amount, paid_by").eq("group_id", group_id).execute().data or []
    splits = supabase.table("expense_splits").select("expense_id, user_id, amount").execute().data or []
    paid = {}
    owed = {}
    for e in exps:
        paid[e.get("paid_by")] = paid.get(e.get("paid_by"), 0.0) + float(e.get("amount", 0))
    for s in splits:
        owed[s.get("user_id")] = owed.get(s.get("user_id"), 0.0) + float(s.get("amount", 0))
    users = set([u for u in paid.keys()] + [u for u in owed.keys()])
    balances = [{"user_id": u, "balance": round(paid.get(u, 0.0) - owed.get(u, 0.0), 2)} for u in users]
    return {"balances": balances}

@router.post("/groups/{group_id}/settlements", summary="Record settlement payments", tags=["Settlements"])
def record_settlements(group_id: str, items: List[dict], user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    to_insert = []
    for it in items:
        to_insert.append({
            "id": str(uuid.uuid4()),
            "group_id": group_id,
            "payer_id": it.get("payer_id"),
            "payee_id": it.get("payee_id"),
            "amount": it.get("amount"),
            "method": it.get("method"),
            "note": it.get("note"),
            "created_by": user["sub"],  # safe now
        })
    if to_insert:
        res = supabase.table("settlements").insert(to_insert).execute()
        if getattr(res, "error", None):
            raise HTTPException(status_code=500, detail=f"Failed to record settlements: {getattr(res, 'error', None)}")
    return {"msg": "Settlements recorded", "count": len(to_insert)}

@router.get("/groups/{group_id}/settlements", summary="List settlements", tags=["Settlements"])
def list_settlements(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    res = supabase.table("settlements").select("*").eq("group_id", group_id).execute()
    return res.data or []

@router.post("/groups/{group_id}/settlements/suggest", summary="Suggest minimal settlement payments", tags=["Settlements"])
def suggest_settlements(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    exps = supabase.table("expenses").select("id, amount, paid_by").eq("group_id", group_id).execute().data or []
    splits = supabase.table("expense_splits").select("expense_id, user_id, amount").execute().data or []
    paid = {}
    owed = {}
    for e in exps:
        paid[e.get("paid_by")] = paid.get(e.get("paid_by"), 0.0) + float(e.get("amount", 0))
    for s in splits:
        owed[s.get("user_id")] = owed.get(s.get("user_id"), 0.0) + float(s.get("amount", 0))
    users = set([u for u in paid.keys()] + [u for u in owed.keys()])
    balances = {u: round(paid.get(u, 0.0) - owed.get(u, 0.0), 2) for u in users}
    creditors = [[u, amt] for u, amt in balances.items() if amt > 0]
    debtors = [[u, -amt] for u, amt in balances.items() if amt < 0]
    def second_item(v): return v[1]
    creditors.sort(key=second_item, reverse=True)
    debtors.sort(key=second_item, reverse=True)
    suggestions = []
    i = j = 0
    while i < len(creditors) and j < len(debtors):
        cred_user, cred_amt = creditors[i]
        debt_user, debt_amt = debtors[j]
        pay = round(min(cred_amt, debt_amt), 2)
        if pay > 0:
            suggestions.append({"payer_id": debt_user, "payee_id": cred_user, "amount": pay})
            creditors[i][1] = round(cred_amt - pay, 2)
            debtors[j][1] = round(debt_amt - pay, 2)
        if creditors[i][1] <= 0.0001:
            i += 1
        if debtors[j][1] <= 0.0001:
            j += 1
    return {"suggestions": suggestions}

@router.get("/categories", summary="List built-in categories", tags=["Metadata"])
def list_categories() -> List[dict]:
    return [
        {"key": "food", "label": "Food & Dining", "icon": "🍽️"},
        {"key": "groceries", "label": "Groceries", "icon": "🛒"},
        {"key": "rent", "label": "Rent", "icon": "🏠"},
        {"key": "utilities", "label": "Utilities", "icon": "💡"},
        {"key": "transport", "label": "Transport", "icon": "🚌"},
        {"key": "travel", "label": "Travel", "icon": "✈️"},
        {"key": "entertainment", "label": "Entertainment", "icon": "🎬"},
        {"key": "health", "label": "Health", "icon": "🏥"},
        {"key": "shopping", "label": "Shopping", "icon": "🛍️"},
        {"key": "other", "label": "Other", "icon": "📦"},
    ]

@router.post("/expenses/{expense_id}/attachments", summary="Attach receipt (upload to storage)", tags=["Attachments"])
async def add_attachment(expense_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    admin = get_supabase_admin()
    supabase = get_supabase_client()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    obj_name = f"{expense_id}/{uuid.uuid4().hex}{ext}"
    try:
        bucket = admin.storage.from_(RECEIPTS_BUCKET)
        bucket.upload(obj_name, data, {"content_type": file.content_type or "application/octet-stream"})
        public_url = bucket.get_public_url(obj_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    meta = {
        "id": str(uuid.uuid4()),
        "expense_id": expense_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(data),
        "url": public_url,
        "uploaded_by": user["sub"],  # safe now (FK exists)
    }
    supabase.table("attachments").insert(meta).execute()
    return {"attachment_id": meta["id"], "filename": file.filename, "url": public_url}

@router.get("/expenses/{expense_id}/attachments", summary="List attachments", tags=["Attachments"])
def list_attachments(expense_id: str, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    supabase = get_supabase_client()
    res = supabase.table("attachments").select("*").eq("expense_id", expense_id).execute()
    return res.data or []

@router.get("/reports/groups/{group_id}/summary", summary="Group summary report", tags=["Reports"])
def group_summary_report(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    exps = supabase.table("expenses").select("id, amount, category, paid_by").eq("group_id", group_id).execute().data or []
    total = round(sum(float(e.get("amount", 0)) for e in exps), 2)
    by_category = {}
    by_payer = {}
    for e in exps:
        cat = e.get("category") or "uncategorized"
        by_category[cat] = round(by_category.get(cat, 0.0) + float(e.get("amount", 0)), 2)
        payer = e.get("paid_by") or "unknown"
        by_payer[payer] = round(by_payer.get(payer, 0.0) + float(e.get("amount", 0)), 2)
    return {"total": total, "by_category": by_category, "by_payer": by_payer}

@router.get("/reports/groups/{group_id}/summary.pdf", summary="Group summary report (PDF)", tags=["Reports"])
def group_summary_report_pdf(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    exps = supabase.table("expenses").select("id, amount, category, paid_by").eq("group_id", group_id).execute().data or []
    total = round(sum(float(e.get("amount", 0)) for e in exps), 2)
    by_category = {}
    by_payer = {}
    for e in exps:
        cat = e.get("category") or "uncategorized"
        by_category[cat] = round(by_category.get(cat, 0.0) + float(e.get("amount", 0)), 2)
        payer = e.get("paid_by") or "unknown"
        by_payer[payer] = round(by_payer.get(payer, 0.0) + float(e.get("amount", 0)), 2)
    try:
        from reportlab.pdfgen import canvas  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="PDF generation not available: install reportlab")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    c.setFont("Helvetica", 14)
    c.drawString(40, y, f"Group {group_id} Summary")
    y -= 20
    c.drawString(40, y, f"Total: {total}")
    y -= 30
    c.setFont("Helvetica", 12)
    c.drawString(40, y, "By Category:")
    y -= 20
    for cat, amt in by_category.items():
        c.drawString(60, y, f"- {cat}: {amt}")
        y -= 16
    y -= 10
    c.drawString(40, y, "By Payer:")
    y -= 20
    for payer, amt in by_payer.items():
        c.drawString(60, y, f"- {payer}: {amt}")
        y -= 16
    c.showPage()
    c.save()
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=group_{group_id}_summary.pdf"}
    return Response(content=buf.getvalue(), media_type="application/pdf", headers=headers)

@router.get("/reports/users/{user_id}/monthly", summary="User monthly totals", tags=["Reports"])
def user_monthly_report(user_id: str, month: str = Query(..., description="YYYY-MM"), user=Depends(get_current_user)):
    if user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    supabase = get_supabase_client()
    exps = supabase.table("expenses").select("id, amount, date").eq("paid_by", user_id).ilike("date", f"{month}%").execute().data or []
    paid_total = sum(float(e.get("amount", 0)) for e in exps)
    exp_ids = [e["id"] for e in exps]
    owed_total = 0.0
    if exp_ids:
        owed_rows = supabase.table("expense_splits").select("amount, expense_id").in_("expense_id", exp_ids).eq("user_id", user_id).execute().data or []
        owed_total = sum(float(r.get("amount", 0)) for r in owed_rows)
    net = round(paid_total - owed_total, 2)
    return {"user_id": user_id, "month": month, "paid": round(paid_total, 2), "owed": round(owed_total, 2), "net": net}

@router.get("/reports/users/{user_id}/summary.csv", summary="User summary (CSV)", tags=["Reports"])
def user_summary_csv(user_id: str, user=Depends(get_current_user)):
    if user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    supabase = get_supabase_client()
    splits = supabase.table("expense_splits").select("expense_id, amount").eq("user_id", user_id).execute().data or []
    exp_ids = [s["expense_id"] for s in splits]
    by_group = {}
    by_category = {}
    if exp_ids:
        exps = supabase.table("expenses").select("id, group_id, category").in_("id", exp_ids).execute().data or []
        info = {e["id"]: e for e in exps}
        for s in splits:
            e = info.get(s["expense_id"]) or {}
            gid = (e.get("group_id") or "unknown").replace(",", " ")
            cat = (e.get("category") or "uncategorized").replace(",", " ")
            by_group[gid] = round(by_group.get(gid, 0.0) + float(s.get("amount", 0)), 2)
            by_category[cat] = round(by_category.get(cat, 0.0) + float(s.get("amount", 0)), 2)
    lines = ["type,name,amount"]
    for gid, amt in by_group.items():
        lines.append(f"group,{gid},{amt}")
    for cat, amt in by_category.items():
        lines.append(f"category,{cat},{amt}")
    csv_text = "\n".join(lines) + "\n"
    headers = {"Content-Disposition": f"attachment; filename=user_{user_id}_summary.csv"}
    return Response(content=csv_text, media_type="text/csv", headers=headers)

@router.get("/reports/users/{user_id}/summary.pdf", summary="User summary (PDF)", tags=["Reports"])
def user_summary_pdf(user_id: str, user=Depends(get_current_user)):
    if user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        from reportlab.pdfgen import canvas  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="PDF generation not available: install reportlab")
    supabase = get_supabase_client()
    splits = supabase.table("expense_splits").select("expense_id, amount").eq("user_id", user_id).execute().data or []
    exp_ids = [s["expense_id"] for s in splits]
    by_group = {}
    by_category = {}
    if exp_ids:
        exps = supabase.table("expenses").select("id, group_id, category").in_("id", exp_ids).execute().data or []
        info = {e["id"]: e for e in exps}
        for s in splits:
            e = info.get(s["expense_id"]) or {}
            gid = (e.get("group_id") or "unknown")
            cat = (e.get("category") or "uncategorized")
            by_group[gid] = round(by_group.get(gid, 0.0) + float(s.get("amount", 0)), 2)
            by_category[cat] = round(by_category.get(cat, 0.0) + float(s.get("amount", 0)), 2)
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    c.setFont("Helvetica", 14)
    c.drawString(40, y, f"User {user_id} Summary")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(40, y, "By Group:")
    y -= 18
    for gid, amt in by_group.items():
        c.drawString(60, y, f"- {gid}: {amt}")
        y -= 16
    y -= 10
    c.drawString(40, y, "By Category:")
    y -= 18
    for cat, amt in by_category.items():
        c.drawString(60, y, f"- {cat}: {amt}")
        y -= 16
    c.showPage()
    c.save()
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=user_{user_id}_summary.pdf"}
    return Response(content=buf.getvalue(), media_type="application/pdf", headers=headers)

@router.get("/reports/groups/{group_id}/summary.csv", summary="Group summary report (CSV)", tags=["Reports"])
def group_summary_report_csv(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    exps = supabase.table("expenses").select("id, amount, category, paid_by").eq("group_id", group_id).execute().data or []
    total = round(sum(float(e.get("amount", 0)) for e in exps), 2)
    by_category = {}
    by_payer = {}
    for e in exps:
        cat = (e.get("category") or "uncategorized").replace(",", " ")
        by_category[cat] = round(by_category.get(cat, 0.0) + float(e.get("amount", 0)), 2)
        payer = (e.get("paid_by") or "unknown").replace(",", " ")
        by_payer[payer] = round(by_payer.get(payer, 0.0) + float(e.get("amount", 0)), 2)
    lines = ["type,name,amount"]
    lines.append(f"total,,{total}")
    for cat, amt in by_category.items():
        lines.append(f"category,{cat},{amt}")
    for payer, amt in by_payer.items():
        lines.append(f"payer,{payer},{amt}")
    csv_text = "\n".join(lines) + "\n"
    headers = {"Content-Disposition": f"attachment; filename=group_{group_id}_summary.csv"}
    return Response(content=csv_text, media_type="text/csv", headers=headers)
