import base64
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import admin, jobs, market
from .config import get_settings

app = FastAPI(title="Self Analytics API")


@app.middleware("http")
async def password_gate(request: Request, call_next):
    """Single-user protection for hosted deployments. Off when APP_PASSWORD is empty."""
    password = get_settings().app_password
    if password and request.url.path != "/health":
        header = request.headers.get("authorization", "")
        supplied = ""
        if header.startswith("Basic "):
            try:
                supplied = base64.b64decode(header[6:]).decode().split(":", 1)[1]
            except (ValueError, IndexError):
                supplied = ""
        if not secrets.compare_digest(supplied, password):
            return JSONResponse({"detail": "Password required"}, status_code=401, headers={"WWW-Authenticate": "Basic"})
    return await call_next(request)


app.include_router(market.router)
app.include_router(jobs.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"ok": True}
