"""
FinTrack - FastAPI Main Application Entrypoint
File: api/main.py
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.accounts import router as accounts_router
from api.routes.admin import router as admin_router
from api.routes.audit import router as audit_router
from api.routes.auth import router as auth_router
from api.routes.fraud import router as fraud_router
from api.routes.live_sheet import router as live_sheet_router
from api.routes.loans import admin_loan_router, router as loans_router
from api.routes.transfers import router as transfers_router
from database_layer.db import check_postgres_health
from database_layer.mongodb import check_mongo_health

app = FastAPI(
    title="FinTrack Banking System API",
    version="2.0.0",
    description="Enterprise Relational DBMS Banking, Double-Entry Ledger, and Transaction Engine",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Flexible localhost and production CORS configuration
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["System"])
def health_check():
    """System connectivity and health status."""
    pg_ok = check_postgres_health()
    mongo_ok = check_mongo_health()
    return {
        "status": "healthy" if pg_ok else "degraded",
        "databases": {
            "postgresql": "ONLINE" if pg_ok else "OFFLINE",
            "mongodb": "ONLINE" if mongo_ok else "OFFLINE",
        },
        "engine": "FastAPI + PostgreSQL 16 + MongoDB",
    }


# Register domain routers
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(transfers_router)
app.include_router(loans_router)
app.include_router(admin_loan_router)
app.include_router(admin_router)
app.include_router(fraud_router)
app.include_router(audit_router)
app.include_router(live_sheet_router)


@app.get("/docs", include_in_schema=False)
def docs_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")


# Serve React Frontend SPA if dist exists
from pathlib import Path
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_root():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"status": "online", "message": "FinTrack Banking System API"}

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str):
        # Don't intercept API or Swagger routes
        if full_path.startswith("api") or full_path.startswith("openapi.json"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")

        target_file = FRONTEND_DIST / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def api_root():
        return {
            "status": "online",
            "message": "FinTrack Banking System API is running.",
            "docs_url": "/api/docs",
            "health_url": "/api/health"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

