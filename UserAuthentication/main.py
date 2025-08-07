from fastapi import FastAPI
from app.routes import auth
from fastapi.staticfiles import StaticFiles


app = FastAPI()

app.include_router(auth.router)
app.mount("/form", StaticFiles(directory="app/form"), name="form")

@app.get("/")
def read_root():
    return {"msg": "Authentication service is running!"}