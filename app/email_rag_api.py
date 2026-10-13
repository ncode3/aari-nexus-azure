"""Mount this router on the authenticated Nexus API, never on public ingress without auth."""
from __future__ import annotations
import os
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from app.email_rag import EmailRAG
from app.email_intelligence import build_funding_dashboard

router = APIRouter(prefix="/internal/email-intelligence", tags=["email-intelligence"])

def authorize(token: str | None):
    expected = os.getenv("NEXUS_EMAIL_INTELLIGENCE_TOKEN")
    if not expected or not token:
        raise HTTPException(503, "Email intelligence API is not configured")
    import hmac
    if not hmac.compare_digest(token, expected):
        raise HTTPException(403, "Forbidden")

class IngestPayload(BaseModel):
    documents: list[dict] = Field(max_length=500)

class AskPayload(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

def rag():
    return EmailRAG(os.getenv("NEXUS_EMAIL_RAG_DB", "/data/email-intelligence.sqlite"))

@router.post("/ingest")
def ingest(payload: IngestPayload, x_nexus_token: str | None = Header(default=None)):
    authorize(x_nexus_token)
    return {"indexed":rag().ingest(payload.documents)}

@router.post("/retrieve")
def retrieve(payload: AskPayload, x_nexus_token: str | None = Header(default=None)):
    authorize(x_nexus_token)
    return rag().evidence_prompt(payload.question)

@router.get("/funding")
def funding(x_nexus_token: str | None = Header(default=None)):
    authorize(x_nexus_token)
    return build_funding_dashboard()
