from __future__ import annotations

from datetime import datetime
from typing import Any

from model.relational import (
    Analysis,
    Attachment,
    AuditEntry,
    Email,
    EmailStage,
    ExceptionRecord,
    Notification,
    Opportunity,
    OpportunityEvent,
    Review,
)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat(timespec="seconds") + "Z"
    return dt.isoformat(timespec="seconds")


def email_to_dict(email: Email) -> dict[str, Any]:
    return {
        "id": email.id,
        "message_id": email.message_id,
        "from_addr": email.from_addr,
        "subject": email.subject,
        "body": email.body,
        "body_html": email.body_html,
        "received_at": iso(email.received_at),
        "status": email.status,
        "classification": email.classification,
        "confidence": email.confidence,
        "sol_number": email.sol_number,
        "opportunity_id": email.opportunity_id,
        "error": email.error,
        "project_type": email.project_type,
        "bid_quality": email.bid_quality,
        "bid_quality_confidence": email.bid_quality_confidence,
        "bid_quality_rationale": email.bid_quality_rationale,
        "created_at": iso(email.created_at),
        "stages": [
            {
                "id": s.id,
                "email_id": s.email_id,
                "stage": s.stage,
                "status": s.status,
                "detail": s.detail,
                "created_at": iso(s.created_at),
            }
            for s in (email.stages or [])
        ],
        "attachments": [
            {
                "id": a.id,
                "filename": a.filename,
                "size": a.size,
                "status": a.status,
                "note": a.note,
            }
            for a in (email.attachments or [])
        ],
    }


def opportunity_to_dict(opp: Opportunity) -> dict[str, Any]:
    return {
        "id": opp.id,
        "sol_number": opp.sol_number,
        "title": opp.title,
        "agency": opp.agency,
        "due_date": opp.due_date,
        "due_tz": opp.due_tz,
        "status": opp.status,
        "summary": opp.summary,
        "confidence": opp.confidence,
        "assigned_to": opp.assigned_to,
        "created_at": iso(opp.created_at),
        "updated_at": iso(opp.updated_at),
        "chunk_count": opp.chunk_count,
        "project_type": opp.project_type,
        "bid_quality": opp.bid_quality,
    }


def review_to_dict(review: Review, opp: Opportunity | None, analysis: Analysis | None) -> dict[str, Any]:
    payload = analysis.payload if analysis else {}
    return {
        "id": review.id,
        "opp_id": review.opp_id,
        "analysis_id": review.analysis_id,
        "status": review.status,
        "decision": review.decision,
        "notes": review.notes,
        "created_at": iso(review.created_at),
        "completed_at": iso(review.completed_at),
        "sol_number": opp.sol_number if opp else None,
        "title": opp.title if opp else None,
        "due_date": opp.due_date if opp else None,
        "due_tz": opp.due_tz if opp else None,
        "analysis_status": analysis.status if analysis else None,
        "analysis": payload,
    }


def exception_to_dict(exc: ExceptionRecord) -> dict[str, Any]:
    return {
        "id": exc.id,
        "email_id": exc.email_id,
        "reason": exc.reason,
        "status": exc.status,
        "created_at": iso(exc.created_at),
    }


def notification_to_dict(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "type": n.type,
        "message": n.message,
        "read": n.read,
        "created_at": iso(n.created_at),
    }


def audit_to_dict(a: AuditEntry) -> dict[str, Any]:
    return {
        "id": a.id,
        "actor": a.actor,
        "action": a.action,
        "entity": a.entity,
        "detail": a.detail,
        "created_at": iso(a.created_at),
    }


def event_to_dict(e: OpportunityEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "opp_id": e.opp_id,
        "type": e.type,
        "detail": e.detail,
        "created_at": iso(e.created_at),
    }


def analysis_to_dict(a: Analysis) -> dict[str, Any]:
    return {
        "id": a.id,
        "opp_id": a.opp_id,
        "payload": a.payload,
        "status": a.status,
        "created_at": iso(a.created_at),
    }
