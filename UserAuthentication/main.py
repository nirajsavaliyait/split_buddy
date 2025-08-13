from fastapi import FastAPI
import os
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth
from fastapi.openapi.utils import get_openapi


app = FastAPI()

# CORS: allow only configured frontend origins (comma-separated). Use * only for local dev.
_origins = os.getenv("FRONTEND_ORIGINS", "*")
origins = [o.strip() for o in _origins.split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

def custom_openapi():
    # Generate OpenAPI schema and remove any deprecated operations so they don't appear in Swagger
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="SplitBuddy Auth API",
        version="1.0.0",
        description="Authentication microservice for SplitBuddy",
        routes=app.routes,
    )
    paths = openapi_schema.get("paths", {})
    to_delete_paths = []
    for path, methods in list(paths.items()):
        to_delete_methods = []
        for method, operation in list(methods.items()):
            if operation.get("deprecated"):
                to_delete_methods.append(method)
        for m in to_delete_methods:
            del methods[m]
        if not methods:
            to_delete_paths.append(path)
    for p in to_delete_paths:
        del paths[p]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/")
def read_root():
    return {"msg": "Authentication microservice running on port 8001"}

@app.get("/health")
def health():
    return {"status": "ok"}