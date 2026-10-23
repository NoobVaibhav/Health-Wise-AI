"""FastAPI application entry point.  Run:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.errors import ReportError
from app.database.connection import init_db
from app.routers import (
    admin, appointments, auth, billing, catalog, dashboard, profile, lab, doctors, employees, health_history, clinical_intel, patient_assistant, patient_portal, patients, pharmacy,
    prescriptions, reports,
)
from app.services.ocr_service import ocr_is_available
from app.services.safety_filter import DISCLAIMER


DEFAULT_SECRET = "change-me-in-production"
logger = logging.getLogger("healthwise")


def check_secret() -> None:
    """A guessable JWT secret lets anyone forge a login. Refuse it on a real (non-SQLite) database, warn on a local one."""
    settings = get_settings()
    weak = settings.jwt_secret == DEFAULT_SECRET or len(settings.jwt_secret) < 32
    if weak and not settings.database_url.startswith("sqlite"):
        raise RuntimeError("JWT_SECRET is missing or too weak. Set a random value of at least 32 characters in backend/.env.")
    if weak:
        logger.warning("JWT_SECRET is the default or too short. Set a random value of 32+ characters in backend/.env before real use.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_secret()
    init_db()  # create tables on first start
    yield


app = FastAPI(title="HealthWise AI - Hospital Management", version="2.0.0", lifespan=lifespan,
              description=DISCLAIMER)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Basic browser protections; API answers (patient data) are never cached."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api") and request.url.path != "/api/health":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(OverflowError)
async def number_too_large_handler(_: Request, exc: OverflowError):
    """An id or number bigger than the database can hold is a bad request, not a server crash."""
    return JSONResponse(status_code=422, content={"detail": "A number in the request is too large."})


@app.exception_handler(IntegrityError)
async def conflict_handler(_: Request, exc: IntegrityError):
    """Two people saving the same thing at the same moment (for example the same bill number): ask to try again instead of crashing."""
    logger.warning("Database conflict: %s", exc.orig)
    return JSONResponse(status_code=409, content={"detail": "This was changed by someone else at the same moment. Please try again."})


@app.exception_handler(ReportError)
async def report_error_handler(_: Request, exc: ReportError):
    """Turns report-pipeline errors into clear JSON messages the frontend can show directly."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})


for module in (auth, admin, patients, doctors, employees, reports, appointments, prescriptions, pharmacy,
               patient_portal, dashboard, catalog, lab, billing, profile, health_history, clinical_intel, patient_assistant):
    app.include_router(module.router)
app.include_router(doctors.directory)


@app.get("/api/health", tags=["system"])
def health_check():
    return {"status": "ok", "ocr_available": ocr_is_available(), "disclaimer": DISCLAIMER}
