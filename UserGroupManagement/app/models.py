from pydantic import BaseModel, EmailStr
from typing import List, Optional


# This model validates group creation input
class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


# This model validates member addition input
class MemberAdd(BaseModel):
    group_id: str
    user_id: str
    phone_number: str
    relationship_tag: str  # Friend, Roommate, Colleague, Family, Other


# This model represents a list of groups
class GroupList(BaseModel):
    groups: List[str]


# This model represents a list of group members
class MemberList(BaseModel):
    members: List[str]
