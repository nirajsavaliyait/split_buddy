from fastapi import FastAPI

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
from fastapi import FastAPI
from app.routes import group

app = FastAPI()
app.include_router(group.router)

@app.get("/")
def read_root():
    return {"message": "UserGroupManagement microservice running on port 8003"}
