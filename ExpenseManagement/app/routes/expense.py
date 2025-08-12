from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Response
from typing import Optional, List
from app.models import (
    ExpenseCreate,
    ExpenseSplit,
    ExpenseUpdate,
    SplitPreviewRequest,
    SplitCommitRequest,
)
from app.utils import get_supabase_client, get_current_user
from app.authz_utils import ensure_member_or_403, ensure_member_by_expense_or_403
import uuid
from datetime import datetime

router = APIRouter()

@router.post("/groups/{group_id}/expenses", summary="Create an expense in a group", tags=["Expenses"])
def create_expense(expense: ExpenseCreate, group_id: Optional[str] = None, user=Depends(get_current_user)):
    expense_id = str(uuid.uuid4())
    gid = group_id or getattr(expense, "group_id", None)
    if not gid:
        raise HTTPException(status_code=422, detail="group_id is required (path or body)")
    # Ensure caller is a member of the group
    ensure_member_or_403(user["sub"], gid)
    data = {
        "id": expense_id,
        "group_id": gid,
        "created_by": expense.created_by,
        "description": expense.description,
        "amount": expense.amount,
        "currency": expense.currency or "USD",
        "date": (expense.date or datetime.utcnow()).isoformat(),
        "paid_by": expense.paid_by or expense.created_by,
        "category": expense.category,
        "notes": expense.notes,
    }
    supabase = get_supabase_client()
    res = supabase.table("expenses").insert(data).execute()
    if res.status_code != 201:
        raise HTTPException(status_code=500, detail="Failed to create expense")
    return {"expense_id": expense_id, "msg": "Expense created successfully"}


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
    # Soft delete if you have a deleted flag, otherwise hard delete
    res = supabase.table("expenses").delete().eq("id", expense_id).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Failed to delete expense")
    # Also delete splits
    supabase.table("expense_splits").delete().eq("expense_id", expense_id).execute()
    return {"msg": "Expense deleted"}

@router.post("/expenses/{expense_id}/splits", summary="Add a split to an expense", tags=["Expenses"])
def split_expense(split: ExpenseSplit, expense_id: Optional[str] = None, user=Depends(get_current_user)):
    split_id = str(uuid.uuid4())
    eid = expense_id or getattr(split, "expense_id", None)
    if not eid:
        raise HTTPException(status_code=422, detail="expense_id is required (path or body)")
    # Ensure caller is part of the expense's group
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
    if res.status_code != 201:
        raise HTTPException(status_code=500, detail="Failed to split expense")
    return {"split_id": split_id, "msg": "Expense split added successfully"}


@router.get("/groups/{group_id}/expenses", summary="List expenses for a group", tags=["Expenses"])
def get_group_expenses(group_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       sort: Optional[str] = None, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    query = supabase.table("expenses").select("*").eq("group_id", group_id)
    # Simplified pagination using range (Supabase range is inclusive)
    start = (page - 1) * page_size
    end = start + page_size - 1
    if sort == "date_desc":
        query = query.order("date", desc=True)
    elif sort == "date_asc":
        query = query.order("date", desc=False)
    res = query.range(start, end).execute()
    return res.data

# Duplicate route removed; use the paginated endpoint above.

@router.get("/users/{user_id}/expenses", summary="List expenses for a user", tags=["Expenses"])
def get_user_expenses(user_id: str, user=Depends(get_current_user)):
    # Only allow querying own expenses
    if user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    supabase = get_supabase_client()
    res = supabase.table("expense_splits").select("*").eq("user_id", user_id).execute()
    return res.data


# Additional MVP endpoints
@router.get("/expenses/{expense_id}/splits", summary="List splits for an expense", tags=["Splits"])
def list_splits(expense_id: str, user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    supabase = get_supabase_client()
    res = supabase.table("expense_splits").select("user_id, amount, is_settled").eq("expense_id", expense_id).execute()
    return res.data or []


@router.get("/users/{user_id}/balances", summary="User net balance (optionally by group)", tags=["Balances"])
def user_balance(user_id: str, group_id: Optional[str] = Query(None), user=Depends(get_current_user)):
    # Only allow querying own balance
    if user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    supabase = get_supabase_client()
    # If group_id provided, ensure membership and filter within that group
    if group_id:
        ensure_member_or_403(user_id, group_id)
        # Expenses paid by user in group
        exps = supabase.table("expenses").select("id, amount").eq("group_id", group_id).eq("paid_by", user_id).execute().data or []
        paid_total = sum(float(e.get("amount", 0)) for e in exps)
        # Owed amounts for user in splits of expenses in this group
        group_exps = supabase.table("expenses").select("id").eq("group_id", group_id).execute().data or []
        exp_ids = [e["id"] for e in group_exps]
        owed_total = 0.0
        if exp_ids:
            owed_rows = supabase.table("expense_splits").select("amount, expense_id").in_("expense_id", exp_ids).eq("user_id", user_id).execute().data or []
            owed_total = sum(float(r.get("amount", 0)) for r in owed_rows)
        balance = round(paid_total - owed_total, 2)
        return {"user_id": user_id, "group_id": group_id, "balance": balance}
    else:
        # Global: sum of amounts user paid minus amounts user owes across all expenses
        exps = supabase.table("expenses").select("amount").eq("paid_by", user_id).execute().data or []
        paid_total = sum(float(e.get("amount", 0)) for e in exps)
        owed_rows = supabase.table("expense_splits").select("amount").eq("user_id", user_id).execute().data or []
        owed_total = sum(float(r.get("amount", 0)) for r in owed_rows)
        return {"user_id": user_id, "balance": round(paid_total - owed_total, 2)}


# Split preview and commit
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
        # Last participant gets remainder to ensure sum equals total
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
    # Replace existing splits with provided ones
    supabase.table("expense_splits").delete().eq("expense_id", expense_id).execute()
    to_insert = [
        {"id": str(uuid.uuid4()), "expense_id": expense_id, "user_id": s.user_id, "amount": s.amount, "is_settled": False}
        for s in body.splits
    ]
    if to_insert:
        res = supabase.table("expense_splits").insert(to_insert).execute()
        if res.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail="Failed to commit splits")
    return {"msg": "Splits committed", "count": len(to_insert)}


# Group balances and settlements (minimal MVP)
@router.get("/groups/{group_id}/balances", summary="Net balance per member in group", tags=["Balances"])
def group_balances(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    # Fetch expenses and splits
    exps = supabase.table("expenses").select("id, amount, paid_by").eq("group_id", group_id).execute().data or []
    splits = supabase.table("expense_splits").select("expense_id, user_id, amount").execute().data or []
    # Compute per-user balance: paid - owed
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
    # Expected item: { payer_id, payee_id, amount, method?, note? }
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
            "created_by": user["sub"],
        })
    if to_insert:
        supabase.table("settlements").insert(to_insert).execute()
    return {"msg": "Settlements recorded", "count": len(to_insert)}


@router.get("/groups/{group_id}/settlements", summary="List settlements", tags=["Settlements"])
def list_settlements(group_id: str, user=Depends(get_current_user)):
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    res = supabase.table("settlements").select("*").eq("group_id", group_id).execute()
    return res.data or []


@router.post("/groups/{group_id}/settlements/suggest", summary="Suggest minimal settlement payments", tags=["Settlements"])
def suggest_settlements(group_id: str, user=Depends(get_current_user)):
    """Generate a suggested list of payments that settles all balances using a greedy algorithm.

    Positive balance = creditor (should receive), negative balance = debtor (should pay).
    """
    ensure_member_or_403(user["sub"], group_id)
    supabase = get_supabase_client()
    # Compute balances (reuse logic similar to group_balances)
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
    debtors = [[u, -amt] for u, amt in balances.items() if amt < 0]  # positive values for amounts owed
    # Sort largest first
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)
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


# Attachments (stub storage)
@router.post("/expenses/{expense_id}/attachments", summary="Attach receipt (metadata only)", tags=["Attachments"])
def add_attachment(expense_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    ensure_member_by_expense_or_403(user["sub"], expense_id)
    # In real app, upload to storage and save URL; here just save metadata
    supabase = get_supabase_client()
    meta = {
        "id": str(uuid.uuid4()),
        "expense_id": expense_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": 0,
    }
    supabase.table("attachments").insert(meta).execute()
    return {"attachment_id": meta["id"], "filename": file.filename}


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


@router.get("/reports/groups/{group_id}/summary.csv", summary="Group summary report (CSV)", tags=["Reports"])
def group_summary_report_csv(group_id: str, user=Depends(get_current_user)):
    """CSV export of the group summary report.

    Rows: type,name,amount
    - total,,<amount>
    - category,<category>,<amount>
    - payer,<user_id>,<amount>
    """
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
    # Build CSV
    lines = ["type,name,amount"]
    lines.append(f"total,,{total}")
    for cat, amt in by_category.items():
        lines.append(f"category,{cat},{amt}")
    for payer, amt in by_payer.items():
        lines.append(f"payer,{payer},{amt}")
    csv_text = "\n".join(lines) + "\n"
    headers = {"Content-Disposition": f"attachment; filename=group_{group_id}_summary.csv"}
    return Response(content=csv_text, media_type="text/csv", headers=headers)
