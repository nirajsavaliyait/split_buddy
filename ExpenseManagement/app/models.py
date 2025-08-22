from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


# Minimal request payload for creating an expense via path group_id
class ExpenseCreateRequest(BaseModel):
    description: str
    amount: float


# This model validates expense split input
class ExpenseSplit(BaseModel):
    expense_id: str
    user_id: str
    amount: float
    is_settled: Optional[bool] = False


class ExpenseUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    date: Optional[datetime] = None
    paid_by: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


# This model represents an expense record
class Expense(BaseModel):
    id: str
    group_id: str
    created_by: str
    description: str
    amount: float
    currency: Optional[str] = None
    date: Optional[datetime] = None
    paid_by: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


# Split preview/commit models
class SplitParticipant(BaseModel):
    user_id: str
    # Exactly one of percent, shares, or exact_amount should be provided per participant for non-equal modes
    percent: Optional[float] = None
    shares: Optional[float] = None
    exact_amount: Optional[float] = None


class SplitPreviewRequest(BaseModel):
    mode: Literal["equal", "percent", "shares", "exact"] = "equal"
    amount: Optional[float] = None  # if omitted, use expense.amount
    participants: List[SplitParticipant]


class SplitItem(BaseModel):
    user_id: str
    amount: float


class SplitCommitRequest(BaseModel):
    splits: List[SplitItem]
