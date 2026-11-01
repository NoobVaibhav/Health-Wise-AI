"""Insurance and TPA claims: a claim for a final invoice, pre-authorisation, the documents the insurer needs, submission, the insurer's decision and the settlement."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import InsuranceClaim, Invoice, PatientInsurance, User
from app.services import audit_service, finance_service as fin
from app.services.access_service import require_permission
from app.utils.validators import PathId, opt_text, text

router = APIRouter(prefix="/api/claims", tags=["insurance-claims"])
manage = require_permission("claims.manage")
view = require_permission("claims.manage", "billing.view", "billing.report")


class ClaimIn(BaseModel):
    invoice_id: int = Field(ge=1)
    patient_insurance_id: int = Field(ge=1)


class PreauthIn(BaseModel):
    amount: float = Field(gt=0, le=100000000)
    reference: opt_text(60) = None


class AmountDecisionIn(BaseModel):
    approved_amount: float = Field(ge=0, le=100000000)
    reason: opt_text(300) = None


class DocumentIn(BaseModel):
    received: bool


class SubmitIn(BaseModel):
    amount: float = Field(gt=0, le=100000000)


class SettleIn(BaseModel):
    amount: float = Field(gt=0, le=100000000)
    reference: text(60, min_length=2)


def _claim(db: Session, claim_id: int) -> InsuranceClaim:
    c = db.get(InsuranceClaim, claim_id)
    if c is None:
        raise HTTPException(404, "Claim not found.")
    return c


@router.get("")
def claims(status_filter: str | None = None, user: User = Depends(view), db: Session = Depends(get_db)):
    query = select(InsuranceClaim).order_by(InsuranceClaim.id.desc()).limit(200)
    if status_filter:
        query = query.where(InsuranceClaim.status == status_filter)
    return [fin.claim_out(db, c) for c in db.scalars(query)]


@router.get("/summary")
def summary(user: User = Depends(view), db: Session = Depends(get_db)):
    """Claims by status with the amounts that are claimed, approved, rejected and settled."""
    rows: dict[str, dict] = {}
    for c in db.scalars(select(InsuranceClaim)):
        r = rows.setdefault(c.status, {"status": c.status, "count": 0, "claimed": 0.0, "approved": 0.0, "rejected": 0.0, "settled": 0.0})
        r["count"] += 1
        r["claimed"] = fin.money(r["claimed"] + (c.claimed_amount or 0))
        r["approved"] = fin.money(r["approved"] + (c.approved_amount or 0))
        r["rejected"] = fin.money(r["rejected"] + (c.rejected_amount or 0))
        r["settled"] = fin.money(r["settled"] + (c.settled_amount or 0))
    return sorted(rows.values(), key=lambda r: r["status"])


@router.get("/{claim_id}")
def detail(claim_id: PathId, user: User = Depends(view), db: Session = Depends(get_db)):
    return fin.claim_out(db, _claim(db, claim_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create(data: ClaimIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    inv = db.get(Invoice, data.invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found.")
    c = fin.create_claim(db, user, inv, data.patient_insurance_id)
    audit_service.log_action(db, user, "CLAIM_CREATED", "insurance_claim", c.id, request, c.claim_number)
    return fin.claim_out(db, c)


@router.post("/{claim_id}/preauth")
def preauth(claim_id: PathId, data: PreauthIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    c = fin.preauth_request(db, _claim(db, claim_id), user, data.amount, data.reference)
    audit_service.log_action(db, user, "CLAIM_PREAUTH_REQUESTED", "insurance_claim", c.id, request, f"{data.amount:.2f}")
    return fin.claim_out(db, c)


@router.post("/{claim_id}/preauth/decision")
def preauth_decision(claim_id: PathId, data: AmountDecisionIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    c = fin.preauth_decide(db, _claim(db, claim_id), user, data.approved_amount, data.reason)
    audit_service.log_action(db, user, "CLAIM_PREAUTH_DECIDED", "insurance_claim", c.id, request, c.status)
    return fin.claim_out(db, c)


@router.post("/{claim_id}/documents/{doc_id}")
def document(claim_id: PathId, doc_id: PathId, data: DocumentIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    c = fin.mark_document(db, _claim(db, claim_id), user, doc_id, data.received)
    audit_service.log_action(db, user, "CLAIM_DOCUMENT", "insurance_claim", c.id, request, f"doc {doc_id} {data.received}")
    return fin.claim_out(db, c)


@router.post("/{claim_id}/submit")
def submit(claim_id: PathId, data: SubmitIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    c = fin.submit(db, _claim(db, claim_id), user, data.amount)
    audit_service.log_action(db, user, "CLAIM_SUBMITTED", "insurance_claim", c.id, request, f"{data.amount:.2f}")
    return fin.claim_out(db, c)


@router.post("/{claim_id}/decision")
def decision(claim_id: PathId, data: AmountDecisionIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    c = fin.decide(db, _claim(db, claim_id), user, data.approved_amount, data.reason)
    audit_service.log_action(db, user, "CLAIM_DECIDED", "insurance_claim", c.id, request, c.status)
    return fin.claim_out(db, c)


@router.post("/{claim_id}/settle")
def settle(claim_id: PathId, data: SettleIn, request: Request, user: User = Depends(manage), db: Session = Depends(get_db)):
    c = fin.settle(db, _claim(db, claim_id), user, data.amount, data.reference)
    audit_service.log_action(db, user, "CLAIM_SETTLED", "insurance_claim", c.id, request, f"{data.amount:.2f}")
    return fin.claim_out(db, c)
