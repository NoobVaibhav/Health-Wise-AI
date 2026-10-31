"""FastAPI application entry point.  Run:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.errors import ReportError
from app.database.connection import init_db
from app.routers import (
    admin, appointments, auth, billing, catalog, dashboard, profile, lab, doctors, employees, health_history, clinical_intel, patient_assistant, patient_portal, patients, pharmacy,
    prescriptions, reports, trainee, referrals,
)
from app.services.ocr_service import ocr_is_available
from app.services.safety_filter import DISCLAIMER
from app.utils.validation_errors import friendly


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


def check_default_password() -> None:
    """Everyone starts with the same password until they change it, so the built-in one should not stay on a real database."""
    settings = get_settings()
    if settings.default_password == "Welcome@123" and not settings.database_url.startswith("sqlite"):
        logger.warning("DEFAULT_PASSWORD is still the built-in value. Set your own in backend/.env before real use.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_default_password()
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


MAX_JSON_BYTES = 1 * 1024 * 1024            # a request body (not a file) is never this big in this application
MAX_UPLOAD_BYTES = 12 * 1024 * 1024          # a report is limited to 10 MB; the rest is the form around it


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """A body bigger than the limit is refused from its announced size, before it is read into memory (a body sent without a size is not caught here: the proxy in front must limit it)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit():
        limit = MAX_UPLOAD_BYTES if request.headers.get("content-type", "").startswith("multipart/") else MAX_JSON_BYTES
        if int(declared) > limit:
            return JSONResponse(status_code=413, content={"detail": f"The request is too large (at most {limit // (1024 * 1024)} MB)."})
    return await call_next(request)


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


@app.exception_handler(RequestValidationError)
async def invalid_input_handler(_: Request, exc: RequestValidationError):
    """Invalid input is a 422 with plain sentences (see utils/validation_errors.py), never a 500 and never a list of technical codes."""
    try:
        errors = exc.errors()
    except Exception:                                      # the error list itself could not be built (for example an unreadable body)
        errors = [{"type": "json_invalid", "loc": ("body",), "msg": "The request could not be read."}]
    return JSONResponse(status_code=422, content=friendly(errors))


@app.exception_handler(RecursionError)
async def too_deep_handler(_: Request, exc: RecursionError):
    """A request body nested so deeply that it cannot be read is a bad request, not a crash."""
    return JSONResponse(status_code=400, content={"detail": "The request could not be read."})


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
               patient_portal, dashboard, catalog, lab, billing, profile, health_history, clinical_intel, patient_assistant, trainee, referrals):
    app.include_router(module.router)
app.include_router(doctors.directory)


@app.get("/api/health", tags=["system"])
def health_check():
    return {"status": "ok", "ocr_available": ocr_is_available(), "disclaimer": DISCLAIMER}
