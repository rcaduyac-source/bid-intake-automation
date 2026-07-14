from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import get_settings
from core.db import RelSessionLocal, VecSessionLocal
from core.pipeline import create_email_record, run_pipeline

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def load_gmail_credentials() -> Credentials | None:
    """Load user OAuth credentials from token file; refresh if expired."""
    settings = get_settings()
    token_path = Path(settings.gmail_token_path)
    if not token_path.exists():
        logger.warning(
            "Gmail token missing at %s — run: uv run python scripts/gmail_oauth_login.py",
            token_path,
        )
        return None

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        return creds

    logger.warning("Gmail token invalid/expired with no refresh_token — re-run oauth login")
    return None


def build_gmail_service():
    creds = load_gmail_credentials()
    if creds is None:
        return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode_body(payload: dict[str, Any]) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    parts = payload.get("parts") or []
    texts: list[str] = []
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/plain" and part.get("body", {}).get("data"):
            texts.append(
                base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
            )
        elif mime.startswith("multipart/"):
            nested = _decode_body(part)
            if nested:
                texts.append(nested)
    return "\n".join(texts)


def _collect_attachments(service, msg_id: str, payload: dict[str, Any]) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []

    def walk(part: dict[str, Any]) -> None:
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        if filename and body.get("attachmentId"):
            att = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=msg_id, id=body["attachmentId"])
                .execute()
            )
            data = base64.urlsafe_b64decode(att.get("data", ""))
            files.append((filename, data))
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    return files


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value") or ""
    return ""


async def process_unread_once() -> int:
    settings = get_settings()
    if not settings.gmail_enabled:
        return 0

    service = await asyncio.to_thread(build_gmail_service)
    if service is None:
        return 0

    def _list_and_fetch() -> list[dict[str, Any]]:
        listed = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread", maxResults=10)
            .execute()
        )
        messages = listed.get("messages") or []
        out: list[dict[str, Any]] = []
        for m in messages:
            full = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
            out.append(full)
        return out

    messages = await asyncio.to_thread(_list_and_fetch)
    processed = 0

    for msg in messages:
        headers = msg.get("payload", {}).get("headers") or []
        subject = _header(headers, "Subject")
        from_addr = _header(headers, "From")
        date_hdr = _header(headers, "Date")
        try:
            received_at = parsedate_to_datetime(date_hdr) if date_hdr else datetime.utcnow()
            if received_at.tzinfo:
                received_at = received_at.replace(tzinfo=None)
        except Exception:  # noqa: BLE001
            received_at = datetime.utcnow()

        body = _decode_body(msg.get("payload") or {})
        files = await asyncio.to_thread(_collect_attachments, service, msg["id"], msg.get("payload") or {})

        async with RelSessionLocal() as rel, VecSessionLocal() as vec:
            email = await create_email_record(
                rel,
                from_addr=from_addr,
                subject=subject,
                body=body,
                message_id=msg.get("id"),
                received_at=received_at,
                files=files,
            )
            await run_pipeline(rel, vec, email.id)

        def _mark_read() -> None:
            service.users().messages().modify(
                userId="me",
                id=msg["id"],
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

        await asyncio.to_thread(_mark_read)
        processed += 1
        logger.info(
            "gmail.processed message_id=%s from=%r subject=%r",
            msg.get("id"),
            from_addr,
            subject,
        )

    return processed


async def gmail_poll_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    logger.info("Gmail poller started (interval=%ss)", settings.gmail_poll_seconds)
    while not stop_event.is_set():
        try:
            n = await process_unread_once()
            if n:
                logger.info("Processed %s Gmail message(s)", n)
        except Exception:  # noqa: BLE001
            logger.exception("Gmail poll failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.gmail_poll_seconds)
        except asyncio.TimeoutError:
            continue
