from __future__ import annotations

import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from core.extract import chunk_pages, extract_file, is_allowed
from core.openai_client import analyze_bid, classify_content, embed_texts
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
from model.vector import DocumentChunk

settings = get_settings()
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.utcnow()


async def _add_stage(
    session: AsyncSession,
    email_id: int,
    stage: str,
    detail: str,
    status: str = "ok",
) -> None:
    session.add(
        EmailStage(
            email_id=email_id,
            stage=stage,
            status=status,
            detail=detail,
            created_at=_now(),
        )
    )
    # Commit each stage as it completes so the polling frontend can render
    # live pipeline progress (the stage tracker + "Processing" state) instead
    # of the email sitting frozen at "received" until the whole run finishes.
    # This also persists partial progress if a later stage fails.
    await session.commit()


async def _audit(
    session: AsyncSession,
    action: str,
    entity: str = "",
    detail: str = "",
    actor: str = "system",
) -> None:
    session.add(
        AuditEntry(actor=actor, action=action, entity=entity, detail=detail, created_at=_now())
    )


async def _notify(session: AsyncSession, ntype: str, message: str) -> None:
    session.add(Notification(type=ntype, message=message, read=0, created_at=_now()))


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def create_email_record(
    session: AsyncSession,
    *,
    from_addr: str,
    subject: str,
    body: str,
    message_id: str | None = None,
    received_at: datetime | None = None,
    files: list[tuple[str, bytes]] | None = None,
) -> Email:
    """Persist email + attachments on disk; does not run pipeline."""
    Path(settings.attachment_dir).mkdir(parents=True, exist_ok=True)
    mid = message_id or f"msg-{uuid.uuid4().hex[:16]}"
    email = Email(
        message_id=mid,
        from_addr=from_addr,
        subject=subject,
        body=body,
        received_at=received_at or _now(),
        status="received",
        created_at=_now(),
    )
    session.add(email)
    await session.flush()

    for filename, raw in files or []:
        safe = Path(filename).name
        dest_dir = Path(settings.attachment_dir) / str(email.id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / safe
        dest.write_bytes(raw)
        allowed = is_allowed(safe)
        session.add(
            Attachment(
                email_id=email.id,
                filename=safe,
                size=len(raw),
                status="stored" if allowed else "rejected",
                note="" if allowed else "Unsupported file type",
                storage_path=str(dest),
            )
        )

    await _audit(session, "email_received", f"email:{email.id}", subject[:200], actor="WF1")
    await session.commit()

    result = await session.execute(
        select(Email)
        .where(Email.id == email.id)
        .options(selectinload(Email.stages), selectinload(Email.attachments))
    )
    return result.scalar_one()


async def run_pipeline(
    rel: AsyncSession,
    vec: AsyncSession,
    email_id: int,
) -> Email:
    result = await rel.execute(
        select(Email)
        .where(Email.id == email_id)
        .options(selectinload(Email.stages), selectinload(Email.attachments))
    )
    email = result.scalar_one()
    email.status = "received"
    await rel.flush()

    logger.info(
        "pipeline.start email_id=%s from=%r subject=%r attachments=%s body_chars=%s",
        email.id,
        email.from_addr,
        email.subject,
        len(email.attachments or []),
        len(email.body or ""),
    )

    try:
        # 1. Email Intake
        await _add_stage(
            rel,
            email.id,
            "Email Intake",
            "Email received and logged; passed the bid-keyword check; not a duplicate",
        )
        logger.info("pipeline.stage email_id=%s stage=%s ok", email.id, "Email Intake")

        # 2. Secure Intake
        atts = list(email.attachments or [])
        stored = [a for a in atts if a.status == "stored"]
        rejected = [a for a in atts if a.status == "rejected"]
        if not atts:
            detail = "No attachments to check"
        else:
            detail = f"{len(stored)} file(s) accepted"
            if rejected:
                detail += f"; {len(rejected)} rejected ({', '.join(a.filename for a in rejected)})"
        await _add_stage(rel, email.id, "Secure Intake", detail)
        logger.info(
            "pipeline.stage email_id=%s stage=%s detail=%s stored=%s rejected=%s",
            email.id,
            "Secure Intake",
            detail,
            [a.filename for a in stored],
            [a.filename for a in rejected],
        )

        # 3. Document Extraction
        pages: list[dict] = []
        texts: list[str] = []
        if email.body.strip():
            pages.append({"source": "email_body", "page": 1, "text": email.body.strip()})
            texts.append(email.body.strip())

        for att in stored:
            if not att.storage_path or not Path(att.storage_path).exists():
                att.status = "rejected"
                att.note = "Missing file on disk"
                logger.warning(
                    "pipeline.extract email_id=%s file=%s missing_path=%s",
                    email.id,
                    att.filename,
                    att.storage_path,
                )
                continue
            try:
                full, pg = extract_file(att.storage_path, att.filename)
                pages.extend(pg)
                if full:
                    texts.append(full)
                att.note = f"Extracted {len(pg)} page(s)"
                logger.info(
                    "pipeline.extract email_id=%s file=%s pages=%s chars=%s",
                    email.id,
                    att.filename,
                    len(pg),
                    len(full),
                )
            except Exception as exc:  # noqa: BLE001
                att.status = "rejected"
                att.note = f"Extraction failed: {exc}"
                logger.exception(
                    "pipeline.extract_failed email_id=%s file=%s", email.id, att.filename
                )

        combined = "\n\n".join(texts)
        email.extracted_text = combined
        extract_detail = (
            f"Extracted text from {len(stored)} attachment(s) + email body ({len(combined)} chars)"
            if combined
            else "No document text to read"
        )
        await _add_stage(rel, email.id, "Document Extraction", extract_detail)
        logger.info(
            "pipeline.stage email_id=%s stage=%s chars=%s preview=%r",
            email.id,
            "Document Extraction",
            len(combined),
            (combined[:240] + "…") if len(combined) > 240 else combined,
        )

        # Load known sol numbers for classify
        known_rows = await rel.execute(select(Opportunity.sol_number).where(Opportunity.sol_number.is_not(None)))
        known_sols = [r[0] for r in known_rows.all() if r[0]]

        # Hybrid: short → full prompt; long → embed + retrieve later for analyze
        use_rag = _approx_tokens(combined) > settings.short_text_token_threshold
        classify_text = combined
        if use_rag and combined:
            # Prefer start (cover/job info) + middle sample + end so quote PDFs
            # are not dominated by marketing filler pages alone
            head = combined[:10000]
            mid_start = max(0, len(combined) // 2 - 3000)
            mid = combined[mid_start : mid_start + 6000]
            tail = combined[-4000:]
            classify_text = f"{head}\n...\n{mid}\n...\n{tail}"
        logger.info(
            "pipeline.classify_prep email_id=%s use_rag=%s classify_chars=%s known_sols=%s",
            email.id,
            use_rag,
            len(classify_text),
            known_sols,
        )

        # 4. AI Classification
        classification = await classify_content(
            subject=email.subject,
            body=email.body,
            document_text=classify_text,
            known_sol_numbers=known_sols,
            attachment_names=[a.filename for a in stored],
            settings=settings,
        )
        cls = classification.get("classification") or "uncertain"
        conf = float(classification.get("confidence") or 0.5)
        sol = classification.get("sol_number")
        rationale = classification.get("rationale") or ""
        email.classification = cls
        email.confidence = conf
        email.sol_number = sol
        class_detail = (
            f"Classified as {cls} ({int(conf * 100)}% confident)"
            + (f". Rationale: {rationale}" if rationale else "")
        )
        await _add_stage(rel, email.id, "AI Classification", class_detail)
        logger.info(
            "pipeline.classify email_id=%s classification=%s confidence=%.2f sol=%r "
            "title=%r due=%r rationale=%r full_result=%s",
            email.id,
            cls,
            conf,
            sol,
            classification.get("title"),
            classification.get("due_date"),
            rationale,
            classification,
        )

        # 5. Validation & Decision (Routed)
        email.status = "routed"
        route_detail = f"Routed as {cls}"
        needs_attention: list[str] = []
        if not classification.get("due_date") and cls in ("new_solicitation", "existing_update", "uncertain"):
            needs_attention.append("No submission deadline found in the email or documents")
        if conf < 0.6:
            needs_attention.append("Low classification confidence")
        if needs_attention:
            route_detail += ". Needs attention: " + "; ".join(needs_attention)
        await _add_stage(rel, email.id, "Validation & Decision", route_detail)
        logger.info(
            "pipeline.route email_id=%s classification=%s status_next=%s attention=%s",
            email.id,
            cls,
            "archived"
            if cls == "not_bid_related"
            else "exception"
            if cls == "uncertain"
            else "continue",
            needs_attention,
        )

        if cls == "not_bid_related":
            email.status = "archived"
            await _audit(rel, "archived_non_bid", f"email:{email.id}", email.subject, actor="WF5")
            logger.warning(
                "pipeline.stop_non_bid email_id=%s subject=%r rationale=%r",
                email.id,
                email.subject,
                rationale,
            )
            await rel.commit()
            return await _reload_email(rel, email.id)

        if cls == "uncertain":
            email.status = "exception"
            rel.add(
                ExceptionRecord(
                    email_id=email.id,
                    reason=classification.get("rationale")
                    or "Unclear whether this is a bid — needs human triage",
                    status="open",
                    created_at=_now(),
                )
            )
            await _notify(rel, "exception", f"Uncertain email needs triage: {email.subject[:120]}")
            await _audit(rel, "exception_opened", f"email:{email.id}", email.subject, actor="WF5")
            logger.warning(
                "pipeline.stop_uncertain email_id=%s subject=%r rationale=%r",
                email.id,
                email.subject,
                rationale,
            )
            await rel.commit()
            return await _reload_email(rel, email.id)

        # 6. Bid recorded
        opp: Opportunity | None = None
        if cls == "existing_update" and sol:
            row = await rel.execute(select(Opportunity).where(Opportunity.sol_number == sol))
            opp = row.scalar_one_or_none()

        if opp:
            opp.title = classification.get("title") or opp.title
            opp.agency = classification.get("agency") or opp.agency
            opp.due_date = classification.get("due_date") or opp.due_date
            opp.due_tz = classification.get("due_tz") or opp.due_tz
            opp.summary = classification.get("summary") or opp.summary
            opp.confidence = conf
            opp.status = "updated"
            opp.updated_at = _now()
            rel.add(
                OpportunityEvent(
                    opp_id=opp.id,
                    type="update",
                    detail=f"Update from email: {email.subject}",
                    created_at=_now(),
                )
            )
            await _add_stage(rel, email.id, "Update Opportunity", f"Updated opportunity {opp.sol_number or opp.id}")
            await _audit(rel, "opportunity_updated", f"opp:{opp.id}", opp.title, actor="WF6")
            await _notify(rel, "update", f"{opp.sol_number or opp.id}: documents updated")
        else:
            opp = Opportunity(
                sol_number=sol,
                title=classification.get("title") or email.subject or "Untitled opportunity",
                agency=classification.get("agency"),
                due_date=classification.get("due_date"),
                due_tz=classification.get("due_tz"),
                status="new",
                summary=classification.get("summary") or "",
                confidence=conf,
                assigned_to="RFP Team",
                created_at=_now(),
                updated_at=_now(),
            )
            rel.add(opp)
            await rel.flush()
            rel.add(
                OpportunityEvent(
                    opp_id=opp.id,
                    type="created",
                    detail="Opportunity created from inbound email",
                    created_at=_now(),
                )
            )
            if opp.due_date:
                rel.add(
                    OpportunityEvent(
                        opp_id=opp.id,
                        type="calendar",
                        detail=f"Deadline {opp.due_date} {opp.due_tz or ''}".strip(),
                        created_at=_now(),
                    )
                )
            await _add_stage(
                rel,
                email.id,
                "Create Opportunity",
                f"Created opportunity {opp.sol_number or opp.id}",
            )
            await _audit(rel, "opportunity_created", f"opp:{opp.id}", opp.title, actor="WF6")
            await _notify(rel, "assignment", f"New opportunity assigned: {opp.title[:120]}")

        email.opportunity_id = opp.id

        # Open exception if deadline missing on a real bid
        if needs_attention:
            rel.add(
                ExceptionRecord(
                    email_id=email.id,
                    reason="; ".join(needs_attention),
                    status="open",
                    created_at=_now(),
                )
            )
            await _notify(rel, "exception", f"{opp.sol_number or opp.id}: {needs_attention[0]}")

        # 7. Document Indexing
        chunks = chunk_pages(pages)
        embeddings = await embed_texts([c["text"] for c in chunks], settings=settings)
        # Replace prior chunks for this opp when updating
        existing = await vec.execute(select(DocumentChunk).where(DocumentChunk.opp_id == opp.id))
        for old in existing.scalars().all():
            await vec.delete(old)
        await vec.flush()

        for c, emb in zip(chunks, embeddings, strict=False):
            vec.add(
                DocumentChunk(
                    opp_id=opp.id,
                    email_id=email.id,
                    seq=c["seq"],
                    source=c["source"],
                    page=c["page"],
                    text=c["text"],
                    embedding=emb,
                    created_at=_now(),
                )
            )
        await vec.commit()
        opp.chunk_count = len(chunks)
        await _add_stage(rel, email.id, "Document Indexing", f"Indexed {len(chunks)} chunk(s)")
        await _audit(rel, "indexed", f"opp:{opp.id}", f"{len(chunks)} chunks", actor="WF7")

        # 8. AI Bid Analysis
        analyze_text = combined
        if use_rag and chunks:
            # Use first N chunks as stand-in retrieval for analysis context
            analyze_text = "\n\n".join(f"[{c['seq']}] {c['text']}" for c in chunks[:12])

        payload = await analyze_bid(
            title=opp.title,
            sol_number=opp.sol_number,
            document_text=analyze_text or email.body,
            settings=settings,
        )
        analysis = Analysis(
            opp_id=opp.id,
            payload=payload,
            status="pending_review",
            created_at=_now(),
        )
        rel.add(analysis)
        await rel.flush()

        review = Review(
            opp_id=opp.id,
            analysis_id=analysis.id,
            status="open",
            created_at=_now(),
        )
        rel.add(review)
        opp.status = "in_review"

        rec = payload.get("recommendation") or "CONDITIONAL"
        await _add_stage(
            rel,
            email.id,
            "AI Bid Analysis",
            f"AI suggests {rec} — sent to the team for review",
        )
        await _audit(rel, "analysis_written", f"opp:{opp.id}", str(rec), actor="WF8")
        await _notify(
            rel,
            "review",
            f"{opp.sol_number or opp.id}: ready for your review — AI suggests {rec}",
        )

        email.status = "processed"
        await rel.commit()
        logger.info(
            "pipeline.complete email_id=%s classification=%s opp_id=%s recommendation=%s",
            email.id,
            cls,
            opp.id,
            rec,
        )
        return await _reload_email(rel, email.id)

    except Exception as exc:  # noqa: BLE001
        await rel.rollback()
        logger.exception("pipeline.error email_id=%s err=%s", email_id, exc)
        # Re-load and mark error
        email = await _reload_email(rel, email_id)
        email.status = "error"
        email.error = str(exc)
        await _add_stage(rel, email.id, "Validation & Decision", f"Pipeline error: {exc}", status="error")
        await rel.commit()
        raise


async def _reload_email(session: AsyncSession, email_id: int) -> Email:
    result = await session.execute(
        select(Email)
        .where(Email.id == email_id)
        .options(selectinload(Email.stages), selectinload(Email.attachments))
    )
    return result.scalar_one()


SCENARIOS: dict[str, dict[str, Any]] = {
    "new_bid": {
        "from_addr": "procurement@agency.example.gov",
        "subject": "RFP DEMO-2026-R-0099 — Facility Maintenance Services",
        "body": (
            "Please find attached the Request for Proposal DEMO-2026-R-0099 for facility maintenance "
            "services. Proposals are due 2026-10-15 AST. This is a new solicitation."
        ),
        "files": [
            (
                "DEMO-2026-R-0099.txt",
                (
                    "REQUEST FOR PROPOSAL DEMO-2026-R-0099\n"
                    "Facility Maintenance Services\n"
                    "Due date: 2026-10-15\n"
                    "Scope: Preventative maintenance for municipal facilities.\n"
                    "Requirements: licensed contractors, bonding, insurance.\n"
                ).encode(),
            )
        ],
    },
    "amendment": {
        "from_addr": "procurement@agency.example.gov",
        "subject": "Amendment 1 — DEMO-2026-R-0099 due date extended",
        "body": (
            "Amendment/addendum for solicitation DEMO-2026-R-0099. "
            "The due date is extended. Please update your files."
        ),
        "files": [
            (
                "DEMO-2026-R-0099-amd1.txt",
                b"AMENDMENT 1 to DEMO-2026-R-0099\nDue date extended to 2026-10-30 AST.\n",
            )
        ],
    },
    "not_bid": {
        "from_addr": "marketing@equipmentworld.example.com",
        "subject": "Summer sale: 15% off excavator rentals this month",
        "body": "Don't miss our summer rental promotion — 15% off excavators. Reply to schedule a demo.",
        "files": [],
    },
    "uncertain": {
        "from_addr": "j.rivera@municipality.example.gov",
        "subject": "Possible upcoming project — early information",
        "body": (
            "We may have an upcoming project for community facility repairs and would like to know "
            "if your firm would be interested. Details are still being finalized. No solicitation number yet."
        ),
        "files": [],
    },
}


async def run_scenario(rel: AsyncSession, vec: AsyncSession, key: str) -> Email:
    if key not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {key}")
    sc = SCENARIOS[key]
    email = await create_email_record(
        rel,
        from_addr=sc["from_addr"],
        subject=sc["subject"],
        body=sc["body"],
        files=sc.get("files") or [],
    )
    return await run_pipeline(rel, vec, email.id)


def store_upload_bytes(email_id: int, filename: str, data: bytes) -> Path:
    dest_dir = Path(settings.attachment_dir) / str(email_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(filename).name
    dest.write_bytes(data)
    return dest


def clear_attachment_tree(email_id: int) -> None:
    path = Path(settings.attachment_dir) / str(email_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
