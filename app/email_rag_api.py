"""Mount this router on the authenticated Nexus API, never on public ingress without auth."""
from __future__ import annotations
import os
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from app.email_rag import EmailRAG
from app.email_intelligence import build_funding_dashboard
from app.intelligence_policy import prototype_api_allowed

router = APIRouter(prefix="/internal/email-intelligence", tags=["email-intelligence"])

def authorize(token: str | None):
    if not prototype_api_allowed(os.environ):
        raise HTTPException(503, "Intelligence API awaits reviewed SQL and Entra integration")
    expected = os.getenv("NEXUS_EMAIL_INTELLIGENCE_TOKEN")
    if not expected:
        raise HTTPException(503, "Email intelligence API is not configured")
    if not token:
        raise HTTPException(401, "Authentication required")
    import hmac
    if not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
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
