from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
from fastapi import FastAPI
from app.routes import group

app = FastAPI(
    title="SplitBuddy Group Management API",
    description="Endpoints for managing groups, memberships, and invites.",
)

# CORS
import os
_origins = os.getenv("FRONTEND_ORIGINS", "*")
origins = [o.strip() for o in _origins.split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(group.router)

@app.get("/")
def read_root():
    return {"message":"UserGroupManagement microservice running on port 8003"}

@app.get("/health")
def health():
    return {"status": "ok"}
