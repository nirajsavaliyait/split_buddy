from fastapi import FastAPI, Depends, HTTPException
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.routes import router as authz_router

app = FastAPI(
    title="SplitBuddy Authorisation API",
    version="1.0.0",
    description="Read-only authorization helpers (JWT verify, group/expense checks)",
)
security = HTTPBearer()

# CORS
_origins = os.getenv("FRONTEND_ORIGINS", "*")
origins = [o.strip() for o in _origins.split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "mysecret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Dependency to verify JWT
def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/private")
def private_route(payload: dict = Depends(verify_jwt)):
    return {"msg": "You have accessed a protected route!", "user": payload}

@app.get("/")
def root():
    return {"msg": "Authorization microservice running on port 8002"}

app.include_router(authz_router)

@app.get("/health")
def health():
    return {"status": "ok"}
