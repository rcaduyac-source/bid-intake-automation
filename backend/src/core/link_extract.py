from __future__ import annotations

import ipaddress
import logging
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from config import Settings, get_settings
from core.extract import extract_file

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
TRAILING_PUNCT = re.compile(r"[.,;:!?)>\]]+$")
USER_AGENT = "ByrdsonBidIntake/1.0 (+https://byrdsonservices.com)"


def find_urls(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in URL_RE.finditer(text):
        url = TRAILING_PUNCT.sub("", m.group(0).strip())
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def find_urls_from_html(html: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = (tag.get("href") or "").strip()
        if not href.lower().startswith(("http://", "https://")):
            continue
        href = TRAILING_PUNCT.sub("", href)
        if href and href not in seen:
            seen.add(href)
            out.append(href)
    return out


def dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _host_blocked(host: str) -> bool:
    h = (host or "").lower().strip(".")
    if not h:
        return True
    if h in ("localhost", "localhost.localdomain"):
        return True
    if h.endswith(".local") or h.endswith(".internal"):
        return True
    try:
        addr = ipaddress.ip_address(h)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
    except ValueError:
        pass
    return False


def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host or _host_blocked(host):
        return False
    # Resolve hostname and reject private IPs (SSRF guard)
    try:
        for info in socket.getaddrinfo(host, None):
            ip = info[4][0]
            addr = ipaddress.ip_address(ip)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
    except OSError:
        return False
    return True


async def fetch_url_content(url: str, settings: Settings | None = None) -> tuple[bytes, str]:
    """Return (body_bytes, content_type_header)."""
    settings = settings or get_settings()
    if not is_safe_url(url):
        raise ValueError(f"URL blocked by safety policy: {url}")

    timeout = httpx.Timeout(settings.link_fetch_timeout_seconds)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        max_redirects=5,
    ) as client:
        async with client.stream("GET", url, headers=headers) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            chunks: list[bytes] = []
            total = 0
            max_bytes = settings.link_fetch_max_bytes
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"URL exceeds max size ({max_bytes} bytes): {url}")
                chunks.append(chunk)
            return b"".join(chunks), content_type


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def _guess_filename(url: str, content_type: str) -> str:
    path = urlparse(url).path or ""
    name = Path(path).name
    if name and "." in name:
        return name
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return "download.pdf"
    if "wordprocessingml" in ct or "msword" in ct:
        return "download.docx"
    if "plain" in ct:
        return "download.txt"
    if "html" in ct:
        return "page.html"
    return "download.bin"


def extract_from_bytes(
    url: str,
    content: bytes,
    content_type: str,
    dest_dir: Path | None = None,
) -> tuple[str, list[dict]]:
    """Return (full_text, pages) for fetched URL content."""
    host = urlparse(url).netloc or url
    source = f"link:{host}"
    ct = (content_type or "").lower()
    filename = _guess_filename(url, content_type)

    if "html" in ct or filename.endswith(".html"):
        text = _html_to_text(content.decode("utf-8", errors="replace"))
        return text, [{"source": source, "page": 1, "text": text, "url": url}]

    ext = Path(filename).suffix.lower()
    if ext in (".pdf", ".docx", ".txt") or "pdf" in ct or "word" in ct:
        if dest_dir:
            dest_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^\w.\-]+", "_", filename)[:200]
            path = dest_dir / safe_name
            path.write_bytes(content)
            full, pages = extract_file(path, filename)
            for p in pages:
                p["source"] = source
                p["url"] = url
            return full, pages

    text = content.decode("utf-8", errors="replace").strip()
    if text:
        return text, [{"source": source, "page": 1, "text": text, "url": url}]
    return "", []


async def fetch_and_extract_url(
    url: str,
    *,
    dest_dir: Path | None = None,
    settings: Settings | None = None,
) -> tuple[str, list[dict], str]:
    settings = settings or get_settings()
    content, content_type = await fetch_url_content(url, settings=settings)
    full, pages = extract_from_bytes(url, content, content_type, dest_dir=dest_dir)
    for page in pages:
        page["content_type"] = content_type
    return full, pages, content_type


async def extract_links_from_email(
    *,
    body: str,
    body_html: str | None,
    email_id: int,
    settings: Settings | None = None,
) -> tuple[list[str], list[dict], int]:
    """
    Discover URLs, fetch and extract. Returns (urls_fetched, pages, total_chars).
    """
    settings = settings or get_settings()
    if not settings.link_fetch_enabled:
        return [], [], 0

    urls = find_urls(body)
    if body_html:
        urls.extend(find_urls_from_html(body_html))
    urls = dedupe_urls(urls)[: settings.link_fetch_max_urls]

    if not urls:
        return [], [], 0

    dest_dir = Path(settings.attachment_dir) / str(email_id) / "links"
    all_pages: list[dict] = []
    fetched: list[str] = []
    total_chars = 0

    for url in urls:
        if not is_safe_url(url):
            logger.warning("link_extract.skip_unsafe url=%s", url)
            continue
        try:
            full, pages, content_type = await fetch_and_extract_url(
                url, dest_dir=dest_dir, settings=settings
            )
            if pages:
                all_pages.extend(pages)
                fetched.append(url)
                total_chars += len(full)
                logger.info(
                    "link_extract.ok url=%s chars=%s pages=%s content_type=%s",
                    url,
                    len(full),
                    len(pages),
                    content_type,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("link_extract.failed url=%s err=%s", url, exc)

    return fetched, all_pages, total_chars
