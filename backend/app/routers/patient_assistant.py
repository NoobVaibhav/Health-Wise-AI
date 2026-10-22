"""Patient assistant (chat and voice): a signed-in patient asks about their OWN records.
The patient is found from the login. No patient id is accepted anywhere, and a conversation id of someone else gives 404."""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import PATIENT, get_patient_profile, require_roles
from app.database.connection import get_db
from app.database.models import PatientAssistantConversation, User
from app.schemas.patient_assistant import ChatIn
from app.services import audit_service, patient_assistant as service
from app.services.assistant_text import LANGUAGES, normalise_lang, t

router = APIRouter(prefix="/api/patient-assistant", tags=["patient-assistant"])
patient_only = require_roles(PATIENT)

_recent: dict[int, deque] = defaultdict(deque)


def _rate_limit(user_id: int) -> None:
    """At most `assistant_rate_per_minute` messages per patient per minute (in this server process)."""
    now, window = time.monotonic(), _recent[user_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= get_settings().assistant_rate_per_minute:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "You are sending messages very quickly. Please wait a moment and try again.")
    window.append(now)


def _conversation(db: Session, user: User, conversation_id: int) -> PatientAssistantConversation:
    conv = service.own_conversation(db, get_patient_profile(db, user), conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    return conv


@router.get("/info")
def info(lang: str = "en", user: User = Depends(patient_only)):
    lang = normalise_lang(lang)
    return {"languages": [{"code": k, "name": v} for k, v in LANGUAGES.items()], "disclaimer": t("disclaimer", lang),
            "ai_wording_available": service.llm_service.llm_is_configured(), "emergency_number": get_settings().emergency_number,
            "retention_days": get_settings().assistant_retention_days}


@router.get("/suggestions")
def suggestions(lang: str = "en", user: User = Depends(patient_only), db: Session = Depends(get_db)):
    return {"suggestions": service.suggestions(db, get_patient_profile(db, user), lang)}


@router.post("/chat")
def chat(data: ChatIn, request: Request, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    patient = get_patient_profile(db, user)
    _rate_limit(user.id)
    try:
        result = service.chat(db, patient, data.message, data.language, data.conversation_id, data.ai_consent)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    # the audit row names the conversation and the kind of question, never the question or the answer
    audit_service.log_action(db, user, "PATIENT_ASSISTANT_CHAT", "assistant_conversation", result["conversation_id"], request,
                             details=f"intent={result['reply']['intent']} safety={result['reply']['safety'] or '-'}")
    return {**result, "disclaimer": t("disclaimer", normalise_lang(data.language))}


@router.get("/conversations")
def conversations(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    patient = get_patient_profile(db, user)
    service.purge_old(db, patient)
    rows = db.scalars(select(PatientAssistantConversation).where(PatientAssistantConversation.patient_id == patient.id)
                      .order_by(PatientAssistantConversation.updated_at.desc()).limit(50)).all()
    return [{"id": c.id, "title": c.title, "language": c.language, "updated_at": c.updated_at.isoformat()} for c in rows]


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: int, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    conv = _conversation(db, user, conversation_id)
    return {"id": conv.id, "title": conv.title, "language": conv.language, "messages": [service.message_out(m) for m in conv.messages]}


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, request: Request, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    conv = _conversation(db, user, conversation_id)
    db.delete(conv)
    db.commit()
    audit_service.log_action(db, user, "PATIENT_ASSISTANT_DELETE", "assistant_conversation", conversation_id, request)
