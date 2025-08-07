from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os

app = FastAPI()
security = HTTPBearer()

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
    return {"msg": "Authorization Service Root"}
