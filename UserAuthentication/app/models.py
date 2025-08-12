from pydantic import BaseModel, EmailStr, field_validator
from pydantic import ValidationInfo
import re

# This model validates user creation input
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str = ""
    last_name: str = ""

    # This logic validates password rules
    @field_validator('password')
    def password_strong(cls, v: str):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain an uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain a lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain a digit')
        if not re.search(r'[^A-Za-z0-9]', v):
            raise ValueError('Password must contain a special character')
        return v

# This model is used to update user profile fields
class UserProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None

# This model validates user login input
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# This model is for email verification
class EmailVerification(BaseModel):
    token: str

# This model is for password reset request
class PasswordResetRequest(BaseModel):
    email: EmailStr

# This model is for password reset
class PasswordReset(BaseModel):
    token: str
    new_password: str

# This model validates group member creation input

# This model validates group member creation input for group_members table
# - group_id and user_id are mandatory (NOT NULL in DB)
# - phone_number and relationship_tag are optional, but default to '' and 'member' respectively
#   (so you can set custom values for role or contact info per member)

# This model validates group member creation input for group_members table
# - group_id, user_id, phone_number, and relationship_tag are all mandatory (NOT NULL in DB)
#   (when a user accepts an invitation, they must provide phone number and relationship tag)
class GroupMemberCreate(BaseModel):
    group_id: str  # Must always be provided, NOT NULL in DB
    user_id: str   # Must always be provided, NOT NULL in DB
    phone_number: str  # Must always be provided, NOT NULL in DB
    relationship_tag: str  # Must always be provided, NOT NULL in DB

    # This logic ensures all required fields are present and not empty
    @field_validator('group_id', 'user_id', 'phone_number', 'relationship_tag')
    def not_empty(cls, v: str, info: ValidationInfo):
        if not v:
            # info.field_name is available in ValidationInfo for pydantic v2
            field_name = getattr(info, 'field_name', 'field')
            raise ValueError(f"{field_name} is required")
        return v

# This model validates group creation input

# This model validates group creation input for groups table
# - name and created_by are mandatory (NOT NULL in DB)
# - description is optional
class GroupCreate(BaseModel):
    name: str = ''  # Default to empty string if not provided, NOT NULL in DB
    description: str = None  # Optional, can be NULL in DB
    created_by: str  # Must always be provided, NOT NULL in DB

    # This logic ensures required fields are present and not empty
    @field_validator('created_by')
    def not_empty(cls, v: str):
        if not v:
            raise ValueError("created_by is required")
        return v
