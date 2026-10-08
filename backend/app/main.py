"""FastAPI application entry point.  Run:  uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import ReportError
from app.database.connection import init_db
from app.routers import (
    admin, appointments, auth, dashboard, doctors, employees, patient_portal, patients, pharmacy, prescriptions,
    reports,
)
from app.services.ocr_service import ocr_is_available
from app.services.safety_filter import DISCLAIMER


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create tables on first start
    yield


app = FastAPI(title="HealthWise AI - Hospital Management", version="2.0.0", lifespan=lifespan,
              description=DISCLAIMER)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(ReportError)
async def report_error_handler(_: Request, exc: ReportError):
    """Turns report-pipeline errors into clear JSON messages the frontend can show directly."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})


for module in (auth, admin, patients, doctors, employees, reports, appointments, prescriptions, pharmacy,
               patient_portal, dashboard):
    app.include_router(module.router)
app.include_router(doctors.directory)


@app.get("/api/health", tags=["system"])
def health_check():
    return {"status": "ok", "ocr_available": ocr_is_available(), "disclaimer": DISCLAIMER}
