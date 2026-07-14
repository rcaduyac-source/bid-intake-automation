from __future__ import annotations

from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from core.db import get_rel_db, get_vec_db
from core.openai_client import answer_question, embed_texts
from core.pipeline import create_email_record, run_pipeline, run_scenario
from core.serializers import email_to_dict
from core.state import build_state, chunks_for_opp, opportunity_detail
from model.relational import (
    Analysis,
    AuditEntry,
    ExceptionRecord,
    Notification,
    Opportunity,
    OpportunityEvent,
    Review,
)
from model.vector import DocumentChunk

router = APIRouter(prefix="/api")

# Set from app lifespan
SERVER_STARTED: datetime | None = None


class DecideBody(BaseModel):
    decision: str = Field(pattern="^(GO|NO-GO|CONDITIONAL)$")
    notes: str = ""


class AskBody(BaseModel):
    question: str


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/state")
async def get_state(rel: AsyncSession = Depends(get_rel_db)):
    state = await build_state(rel)
    state["ops"]["server_started"] = (
        SERVER_STARTED.isoformat(timespec="seconds") + "Z" if SERVER_STARTED else None
    )
    return state


@router.get("/opportunities/{opp_id}")
async def get_opportunity(
    opp_id: int,
    rel: AsyncSession = Depends(get_rel_db),
    vec: AsyncSession = Depends(get_vec_db),
):
    detail = await opportunity_detail(rel, vec, opp_id)
    if not detail:
        raise HTTPException(404, "Opportunity not found")
    chunks = await chunks_for_opp(vec, opp_id)
    return {"opportunity": detail, "chunks": chunks}


@router.post("/emails")
async def submit_email(
    from_addr: str = Form(...),
    subject: str = Form(...),
    body: str = Form(""),
    files: Annotated[list[UploadFile] | None, File()] = None,
    rel: AsyncSession = Depends(get_rel_db),
    vec: AsyncSession = Depends(get_vec_db),
):
    file_tuples: list[tuple[str, bytes]] = []
    for f in files or []:
        raw = await f.read()
        file_tuples.append((f.filename or "upload.bin", raw))

    email = await create_email_record(
        rel,
        from_addr=from_addr,
        subject=subject,
        body=body,
        files=file_tuples,
    )
    email = await run_pipeline(rel, vec, email.id)
    return email_to_dict(email)


@router.post("/simulate/{scenario}")
async def simulate(
    scenario: str,
    rel: AsyncSession = Depends(get_rel_db),
    vec: AsyncSession = Depends(get_vec_db),
):
    try:
        email = await run_scenario(rel, vec, scenario)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return email_to_dict(email)


@router.post("/reviews/{review_id}/decide")
async def decide_review(
    review_id: int,
    body: DecideBody,
    rel: AsyncSession = Depends(get_rel_db),
):
    review = (
        await rel.execute(select(Review).where(Review.id == review_id))
    ).scalar_one_or_none()
    if not review:
        raise HTTPException(404, "Review not found")
    if review.status != "open":
        raise HTTPException(400, "Review already completed")

    review.status = "done"
    review.decision = body.decision
    review.notes = body.notes or ""
    review.completed_at = datetime.utcnow()

    opp = (
        await rel.execute(select(Opportunity).where(Opportunity.id == review.opp_id))
    ).scalar_one_or_none()
    if opp:
        opp.status = (
            "go_approved"
            if body.decision == "GO"
            else "no_go"
            if body.decision == "NO-GO"
            else "conditional"
        )
        opp.updated_at = datetime.utcnow()
        rel.add(
            OpportunityEvent(
                opp_id=opp.id,
                type="decision",
                detail=f"Human decision {body.decision}",
                created_at=datetime.utcnow(),
            )
        )

    analysis = (
        await rel.execute(select(Analysis).where(Analysis.id == review.analysis_id))
    ).scalar_one_or_none()
    if analysis:
        analysis.status = "confirmed"

    rel.add(
        Notification(
            type="decision",
            message=f"{(opp.sol_number if opp else '')}: human decision {body.decision}",
            read=0,
            created_at=datetime.utcnow(),
        )
    )
    rel.add(
        AuditEntry(
            actor="Reviewer",
            action="review_completed",
            entity=f"review:{review.id}",
            detail=body.decision,
            created_at=datetime.utcnow(),
        )
    )
    await rel.commit()
    return {"ok": True, "decision": body.decision}


@router.post("/exceptions/{exc_id}/resolve")
async def resolve_exception(exc_id: int, rel: AsyncSession = Depends(get_rel_db)):
    exc = (
        await rel.execute(select(ExceptionRecord).where(ExceptionRecord.id == exc_id))
    ).scalar_one_or_none()
    if not exc:
        raise HTTPException(404, "Exception not found")
    exc.status = "resolved"
    await rel.commit()
    return {"ok": True}


@router.post("/opportunities/{opp_id}/approve")
async def approve_opportunity(opp_id: int, rel: AsyncSession = Depends(get_rel_db)):
    opp = (
        await rel.execute(select(Opportunity).where(Opportunity.id == opp_id))
    ).scalar_one_or_none()
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    if opp.status not in ("go_approved", "conditional"):
        raise HTTPException(400, "Opportunity is not approved for proposal phase")
    opp.status = "proposal_phase"
    opp.updated_at = datetime.utcnow()
    rel.add(
        OpportunityEvent(
            opp_id=opp.id,
            type="approved",
            detail="Moved to proposal phase",
            created_at=datetime.utcnow(),
        )
    )
    await rel.commit()
    return {"ok": True}


@router.post("/opportunities/{opp_id}/ask")
async def ask_documents(
    opp_id: int,
    body: AskBody,
    vec: AsyncSession = Depends(get_vec_db),
):
    settings = get_settings()
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "question required")

    rows = (
        await vec.execute(select(DocumentChunk).where(DocumentChunk.opp_id == opp_id))
    ).scalars().all()
    if not rows:
        return {"answer": "No indexed documents for this opportunity.", "sources": []}

    # Vector search when embeddings exist; fallback to keyword rank
    query_emb = (await embed_texts([q], settings=settings))[0]
    scored: list[tuple[float, DocumentChunk]] = []
    for c in rows:
        if c.embedding is not None:
            # cosine similarity via python (small n)
            a = list(c.embedding)
            dot = sum(x * y for x, y in zip(a, query_emb, strict=False))
            na = sum(x * x for x in a) ** 0.5 or 1.0
            nb = sum(x * x for x in query_emb) ** 0.5 or 1.0
            score = dot / (na * nb)
        else:
            words = set(q.lower().split())
            t = (c.text or "").lower()
            score = float(sum(1 for w in words if len(w) > 2 and w in t))
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:4]
    context = [
        {
            "seq": c.seq,
            "source": c.source,
            "page": c.page,
            "text": c.text,
            "score": float(s),
        }
        for s, c in top
        if s > 0
    ]
    if not context:
        context = [
            {
                "seq": c.seq,
                "source": c.source,
                "page": c.page,
                "text": c.text,
                "score": 0,
            }
            for _, c in scored[:3]
        ]

    return await answer_question(question=q, context_chunks=context, settings=settings)
