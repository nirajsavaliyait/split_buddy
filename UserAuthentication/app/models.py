from pydantic import BaseModel, EmailStr, validator
import re

# This model validates user creation input
class UserCreate(BaseModel):
    email: EmailStr
    password: str

    # This logic validates password rules
    @validator('password')
    def password_strong(cls, v):
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
