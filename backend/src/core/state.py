from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from core.serializers import (
    analysis_to_dict,
    audit_to_dict,
    email_to_dict,
    event_to_dict,
    exception_to_dict,
    notification_to_dict,
    opportunity_to_dict,
    review_to_dict,
)
from model.relational import (
    Analysis,
    AuditEntry,
    Email,
    EmailStage,
    ExceptionRecord,
    Notification,
    Opportunity,
    Review,
)
from model.vector import DocumentChunk


async def build_state(rel: AsyncSession) -> dict:
    settings = get_settings()
    since = datetime.utcnow() - timedelta(hours=24)

    emails = (
        await rel.execute(
            select(Email)
            .options(selectinload(Email.stages), selectinload(Email.attachments))
            .order_by(Email.id.desc())
        )
    ).scalars().all()

    opps = (
        await rel.execute(select(Opportunity).order_by(Opportunity.id.desc()))
    ).scalars().all()

    reviews = (await rel.execute(select(Review).order_by(Review.id.desc()))).scalars().all()
    analyses = {
        a.id: a
        for a in (await rel.execute(select(Analysis))).scalars().all()
    }
    opp_by_id = {o.id: o for o in opps}

    exceptions = (
        await rel.execute(select(ExceptionRecord).order_by(ExceptionRecord.id.desc()))
    ).scalars().all()
    notifications = (
        await rel.execute(select(Notification).order_by(Notification.id.desc()).limit(50))
    ).scalars().all()
    audit = (
        await rel.execute(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(100))
    ).scalars().all()

    emails_24h = (
        await rel.execute(select(func.count()).select_from(Email).where(Email.created_at >= since))
    ).scalar_one()
    stages_24h = (
        await rel.execute(
            select(func.count()).select_from(EmailStage).where(EmailStage.created_at >= since)
        )
    ).scalar_one()
    errors_24h = (
        await rel.execute(
            select(func.count()).select_from(Email).where(Email.status == "error", Email.created_at >= since)
        )
    ).scalar_one()
    open_exc = sum(1 for e in exceptions if e.status == "open")
    open_rev = sum(1 for r in reviews if r.status == "open")

    return {
        "emails": [email_to_dict(e) for e in emails],
        "opportunities": [opportunity_to_dict(o) for o in opps],
        "reviews": [
            review_to_dict(r, opp_by_id.get(r.opp_id), analyses.get(r.analysis_id)) for r in reviews
        ],
        "exceptions": [exception_to_dict(e) for e in exceptions],
        "notifications": [notification_to_dict(n) for n in notifications],
        "audit": [audit_to_dict(a) for a in audit],
        "ops": {
            "ai_mode": settings.ai_mode,
            "ai_model": settings.ai_model_label,
            "ai_last_error": "",
            "server_started": None,
            "flows_active": True,
            "emails_24h": emails_24h,
            "executions_24h": stages_24h,
            "errors_24h": errors_24h,
            "open_exceptions": open_exc,
            "open_reviews": open_rev,
        },
        "scenarios": {
            "new_bid": "New solicitation (RFP w/ PDF)",
            "amendment": "Amendment (existing update)",
            "not_bid": "Non-bid email (archived)",
            "uncertain": "Ambiguous (low confidence)",
        },
    }


async def opportunity_detail(rel: AsyncSession, vec: AsyncSession, opp_id: int) -> dict | None:
    opp = (
        await rel.execute(
            select(Opportunity)
            .where(Opportunity.id == opp_id)
            .options(selectinload(Opportunity.events), selectinload(Opportunity.analyses))
        )
    ).scalar_one_or_none()
    if not opp:
        return None

    chunks = (
        await vec.execute(
            select(DocumentChunk)
            .where(DocumentChunk.opp_id == opp_id)
            .order_by(DocumentChunk.seq)
        )
    ).scalars().all()

    detail = opportunity_to_dict(opp)
    detail["events"] = [event_to_dict(e) for e in (opp.events or [])]
    detail["analyses"] = [analysis_to_dict(a) for a in (opp.analyses or [])]
    detail["chunks"] = [
        {
            "id": c.id,
            "source": c.source,
            "seq": c.seq,
            "page": c.page,
            "preview": (c.text or "")[:240],
        }
        for c in chunks
    ]
    return detail


async def chunks_for_opp(vec: AsyncSession, opp_id: int) -> list[dict]:
    rows = (
        await vec.execute(
            select(DocumentChunk).where(DocumentChunk.opp_id == opp_id).order_by(DocumentChunk.seq)
        )
    ).scalars().all()
    return [
        {
            "opp_id": c.opp_id,
            "seq": c.seq,
            "source": c.source,
            "page": c.page,
            "text": c.text,
        }
        for c in rows
    ]
