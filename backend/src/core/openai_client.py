from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from config import Settings, get_settings

logger = logging.getLogger(__name__)

CLASSIFY_SCHEMA_HINT = """
Return JSON with keys:
- classification: one of new_solicitation, existing_update, not_bid_related, uncertain
- confidence: number 0-1
- sol_number: string or null
- title: short title string
- agency: string or null
- due_date: YYYY-MM-DD or null
- due_tz: timezone string or null
- summary: 1-3 sentence summary
- rationale: short reason for classification

Byrdson bid-intake context (construction / facilities / roofing / services):
Treat ANY of the following as a BIDS / work opportunity → classify new_solicitation
(or existing_update if it clearly amends a known solicitation number):
- Formal RFPs, RFQs, IFBs, invitations to bid, public solicitations
- Proposals, quotes, estimates, contracts, scopes of work, or pricing packages
  sent for Byrdson to review, respond to, price, or perform
- Client / owner / GC / homeowner requests for work, bids, or proposals
- Forwarded quote/proposal PDFs (e.g. roofing quotes, contractor proposals) —
  even if the email body is short ("please review") or subject says "proposal"/"quote"/"contract"
- "Proposal" and "quote" are equivalent to a bid opportunity for this classifier

Use not_bid_related ONLY for clear non-work mail:
- Pure marketing newsletters, cold ads with no job site / quote / contract attachment
- Spam, phishing, or unrelated personal mail
- Generic product catalogs with no ask for Byrdson to bid or review a job

If a PDF quote/proposal/contract is attached, do NOT call it marketing —
prefer new_solicitation. If details are thin but it looks like work, prefer uncertain
over not_bid_related.
"""

ANALYZE_SCHEMA_HINT = """
Return JSON with keys:
- requirements: array of {text, cite} where cite is chunk seq or 0
- risks: array of {text, cite}
- findings: array of {text, cite}
- scope: short string
- recommendation: GO | NO-GO | CONDITIONAL
- rationale: short string
"""

BID_QUALITY_SCHEMA_HINT = """
Return JSON with keys:
- project_type: one of residential, commercial, mixed, institutional, other
- bid_quality: one of good_bid, bad_bid, uncertain
- confidence: number 0-1
- rationale: short reason

Byrdson only pursues RESIDENTIAL work. Rules:
- good_bid: residential projects — single-family homes, multi-family housing, condos/townhomes,
  homeowner roofing/HVAC/plumbing quotes, home repair/reconstruction (e.g. CDBG home programs),
  residential roofing proposals sent for Byrdson to price or perform
- bad_bid: non-residential — commercial office/retail, municipal/public works RFPs, schools,
  hospitals, highways, industrial, institutional, general commercial GC work
- mixed: if primarily housing units → good_bid; if primarily commercial/public → bad_bid
- uncertain: cannot tell from available text — use when confidence is low

Prefer uncertain over bad_bid when evidence is thin. A homeowner roofing quote PDF is good_bid.
A municipal department RFP for public infrastructure is bad_bid.
"""


def _client(settings: Settings | None = None) -> AsyncOpenAI | None:
    settings = settings or get_settings()
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _heuristic_classify(subject: str, body: str, text: str) -> dict[str, Any]:
    blob = f"{subject}\n{body}\n{text}".lower()
    sol = None
    m = re.search(r"\b([A-Z]{2,10}[-_]?\d{2,4}[-_][A-Z]?\d{2,6})\b", f"{subject} {body} {text}")
    if m:
        sol = m.group(1)

    bid_keywords = ("rfp", "rfq", "ifb", "solicitation", "bid", "proposal", "amendment", "addendum", "quote", "contract", "estimate", "scope of work")
    hits = sum(1 for k in bid_keywords if k in blob)
    has_job_doc = any(
        k in blob for k in ("quote", "proposal", "contract", "estimate", "roofing", "rfp", "bid")
    )
    if "amendment" in blob or "addendum" in blob or "revised" in blob:
        cls = "existing_update"
        conf = 0.75
    elif hits >= 1 or sol or has_job_doc:
        cls = "new_solicitation"
        conf = 0.7 if sol or has_job_doc else 0.55
    elif hits == 0 and "sale" in blob and not has_job_doc:
        cls = "not_bid_related"
        conf = 0.85
    else:
        cls = "uncertain"
        conf = 0.5

    title = subject.strip() or (sol or "Untitled opportunity")
    return {
        "classification": cls,
        "confidence": conf,
        "sol_number": sol,
        "title": title[:200],
        "agency": None,
        "due_date": None,
        "due_tz": None,
        "summary": (body or text)[:400],
        "rationale": "Heuristic classification (no OPENAI_API_KEY).",
    }


def _heuristic_analyze(text: str) -> dict[str, Any]:
    excerpt = (text or "")[:500]
    return {
        "requirements": [{"text": "Review solicitation requirements in source documents.", "cite": 1}],
        "risks": [{"text": "Deadline or scope may need human confirmation.", "cite": 0}],
        "findings": [{"text": excerpt or "Limited document text available.", "cite": 1}],
        "scope": "See email and attachments.",
        "recommendation": "CONDITIONAL",
        "rationale": "Mock analysis — set OPENAI_API_KEY for live AI.",
    }


def _heuristic_bid_quality(subject: str, body: str, text: str) -> dict[str, Any]:
    blob = f"{subject}\n{body}\n{text}".lower()
    residential_kw = (
        "residential", "homeowner", "single-family", "single family", "multi-family",
        "multifamily", "housing", "home repair", "roofing quote", "condo", "townhome",
        "dwelling", "house", "cdbg", "home reconstruction",
    )
    commercial_kw = (
        "municipal", "department of", "public works", "highway", "school district",
        "hospital", "commercial building", "office building", "retail", "industrial",
        "rfp no", "solicitation no", "ifb", "state of", "county of", "city of",
        "infrastructure", "prdo", "agency",
    )
    res_hits = sum(1 for k in residential_kw if k in blob)
    com_hits = sum(1 for k in commercial_kw if k in blob)

    if res_hits > com_hits and res_hits >= 1:
        return {
            "project_type": "residential",
            "bid_quality": "good_bid",
            "confidence": min(0.55 + res_hits * 0.08, 0.85),
            "rationale": "Heuristic: residential keywords detected.",
        }
    if com_hits > res_hits and com_hits >= 1:
        return {
            "project_type": "commercial",
            "bid_quality": "bad_bid",
            "confidence": min(0.55 + com_hits * 0.08, 0.85),
            "rationale": "Heuristic: commercial/municipal keywords detected.",
        }
    return {
        "project_type": "other",
        "bid_quality": "uncertain",
        "confidence": 0.5,
        "rationale": "Heuristic: could not determine residential vs commercial.",
    }


async def classify_content(
    *,
    subject: str,
    body: str,
    document_text: str,
    known_sol_numbers: list[str] | None = None,
    attachment_names: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    client = _client(settings)
    known = ", ".join(known_sol_numbers or []) or "(none)"
    prompt_text = document_text[:24000]
    att_line = ", ".join(attachment_names or []) or "(none)"

    if not client:
        result = _heuristic_classify(subject, body, f"{att_line}\n{prompt_text}")
        if result["sol_number"] and result["sol_number"] in (known_sol_numbers or []):
            result["classification"] = "existing_update"
        logger.info("classify.heuristic subject=%r result=%s", subject, result)
        return result

    logger.info(
        "classify.openai_request model=%s subject=%r body_chars=%s doc_chars=%s attachments=%s",
        settings.openai_chat_model,
        subject,
        len(body or ""),
        len(prompt_text or ""),
        attachment_names or [],
    )
    resp = await client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You classify inbound construction/services procurement emails for Byrdson bid intake. "
                    + CLASSIFY_SCHEMA_HINT
                    + f" Known solicitation numbers already in the system: {known}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Subject: {subject}\n"
                    f"Attachment filenames: {att_line}\n\n"
                    f"Body:\n{body}\n\n"
                    f"Documents:\n{prompt_text}"
                ),
            },
        ],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or "{}"
    logger.info("classify.openai_raw subject=%r raw=%s", subject, raw[:2000])
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("classify.openai_json_error subject=%r raw=%r", subject, raw[:500])
        result = _heuristic_classify(subject, body, f"{att_line}\n{prompt_text}")
        result["rationale"] = f"JSON parse failed; fallback heuristic. Raw: {raw[:200]}"
    return result


async def screen_bid_quality(
    *,
    subject: str,
    body: str,
    document_text: str,
    attachment_names: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    client = _client(settings)
    prompt_text = document_text[:24000]
    att_line = ", ".join(attachment_names or []) or "(none)"

    if not client:
        result = _heuristic_bid_quality(subject, body, f"{att_line}\n{prompt_text}")
        logger.info("bid_quality.heuristic subject=%r result=%s", subject, result)
        return result

    logger.info(
        "bid_quality.openai_request model=%s subject=%r doc_chars=%s attachments=%s",
        settings.openai_chat_model,
        subject,
        len(prompt_text or ""),
        attachment_names or [],
    )
    resp = await client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You screen bid opportunities for Byrdson Services, a residential-focused contractor. "
                    + BID_QUALITY_SCHEMA_HINT
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Subject: {subject}\n"
                    f"Attachment filenames: {att_line}\n\n"
                    f"Body:\n{body}\n\n"
                    f"Documents:\n{prompt_text}"
                ),
            },
        ],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or "{}"
    logger.info("bid_quality.openai_raw subject=%r raw=%s", subject, raw[:2000])
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("bid_quality.openai_json_error subject=%r raw=%r", subject, raw[:500])
        result = _heuristic_bid_quality(subject, body, f"{att_line}\n{prompt_text}")
        result["rationale"] = f"JSON parse failed; fallback heuristic. Raw: {raw[:200]}"
    return result


async def analyze_bid(
    *,
    title: str,
    sol_number: str | None,
    document_text: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    client = _client(settings)
    prompt_text = document_text[:30000]

    if not client:
        return _heuristic_analyze(prompt_text)

    resp = await client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze bid solicitations for a construction services firm. "
                    + ANALYZE_SCHEMA_HINT
                ),
            },
            {
                "role": "user",
                "content": f"Title: {title}\nSolicitation: {sol_number or 'unknown'}\n\nText:\n{prompt_text}",
            },
        ],
        temperature=0.2,
    )
    return json.loads(resp.choices[0].message.content or "{}")


async def embed_texts(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    settings = settings or get_settings()
    client = _client(settings)
    if not texts:
        return []
    if not client:
        # Deterministic pseudo-embeddings for mock/dev without API key
        dims = settings.openai_embed_dims
        out: list[list[float]] = []
        for t in texts:
            vec = [0.0] * dims
            for i, ch in enumerate(t.encode("utf-8")[:dims]):
                vec[i % dims] += (ch / 255.0) * 0.01
            out.append(vec)
        return out

    resp = await client.embeddings.create(model=settings.openai_embed_model, input=texts)
    return [row.embedding for row in resp.data]


async def answer_question(
    *,
    question: str,
    context_chunks: list[dict],
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    client = _client(settings)
    context = "\n\n".join(
        f"[{c.get('seq')}] ({c.get('source')}, page {c.get('page')}) {c.get('text')}" for c in context_chunks
    )
    sources = [
        {"seq": c.get("seq"), "source": c.get("source"), "page": c.get("page"), "score": c.get("score", 0)}
        for c in context_chunks
    ]

    if not client:
        return {
            "answer": "Here are the most related passages:\n\n" + (context or "No indexed chunks found."),
            "sources": sources,
        }

    resp = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {
                "role": "system",
                "content": "Answer using only the provided document passages. Cite chunk numbers like [1].",
            },
            {"role": "user", "content": f"Question: {question}\n\nPassages:\n{context}"},
        ],
        temperature=0.2,
    )
    return {"answer": resp.choices[0].message.content or "", "sources": sources}
