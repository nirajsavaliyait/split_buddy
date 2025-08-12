from fastapi import FastAPI
from app.routes import auth
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi


app = FastAPI()

app.include_router(auth.router)
app.mount("/form", StaticFiles(directory="app/form"), name="form")

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