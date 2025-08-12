import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import expense

app = FastAPI()

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
app.include_router(expense.router)

@app.get("/")
def read_root():
    return {"message": "ExpenseManagement microservice running on port 8004"}

@app.get("/health")
def health():
    return {"status": "ok"}
