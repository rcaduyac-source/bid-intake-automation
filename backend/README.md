# Bid Intake Backend

FastAPI service that mirrors the frontend bid-intake pipeline: Gmail or manual email → extract → classify (OpenAI) → route → record opportunity → index (pgvector) → analyze → human decide.

## Local run (without Docker)

1. Start Postgres + pgvector (or use `docker compose up postgres pgvector`).
2. Copy `.env.example` → `.env` and fill values.
3. From `backend/`:

```bash
uv sync
cd src && uv run uvicorn main:app --reload --port 8000
```

## Docker (3 services)

```bash
docker compose up --build
```

Services: `backend` (:8000), `postgres` (:5432), `pgvector` (:5433). Compose creates the shared Docker network `bid-intake-net` (frontend joins it afterward).

## Gmail (user OAuth — no Workspace admin)

Does **not** use service-account domain-wide delegation.

### One-time setup in Google Cloud Console

1. Enable **Gmail API**.
2. **APIs & Services → OAuth consent screen**
   - User type: **External**
   - Publishing: **Testing**
   - Add your mailbox as a **Test user** (e.g. `rcaduyac@byrdsonservices.com`)
3. **Credentials → Create credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Download JSON → save as `secrets/gmail_oauth_client.json`

### Authorize once on your Mac (opens browser)

```bash
cd backend
uv sync
# If running Docker, use host paths in .env for this step only, e.g.:
# GMAIL_OAUTH_CLIENT_SECRETS=./secrets/gmail_oauth_client.json
# GMAIL_TOKEN_PATH=./secrets/gmail_token.json
uv run python scripts/gmail_oauth_login.py
```

Sign in as the inbox to poll. This writes `secrets/gmail_token.json` (refresh token).

Then set in `.env`:

```env
GMAIL_ENABLED=true
GMAIL_OAUTH_CLIENT_SECRETS=/app/secrets/gmail_oauth_client.json
GMAIL_TOKEN_PATH=/app/secrets/gmail_token.json
```

Restart backend. The poller uses `userId=me` (the authorized account).

## OpenAI

Set `OPENAI_API_KEY`. Without it the pipeline runs in heuristic **mock** mode.

## Bid quality (residential screening)

After a bid is routed, `Bid Quality Screening` classifies:
- `good_bid` — residential (continues full pipeline)
- `bad_bid` — non-residential (archived early)
- `uncertain` — continues with an exception for human review

```env
BID_QUALITY_ENABLED=true
BID_QUALITY_MIN_CONFIDENCE=0.6
```

Set `BID_QUALITY_ENABLED=false` to skip screening (all bids treated as good).

## Email link extraction

During **Document Extraction**, URLs in the plain-text body and in stored HTML (`body_html` from Gmail) are discovered, fetched (with SSRF guards), and merged into the same text used for classify/analyze/RAG. Supports HTML pages plus linked PDF/DOCX/TXT.

```env
LINK_FETCH_ENABLED=true
LINK_FETCH_MAX_URLS=5
LINK_FETCH_TIMEOUT_SECONDS=15
LINK_FETCH_MAX_BYTES=10485760
```

Set `LINK_FETCH_ENABLED=false` to skip HTTP fetches (body + attachments only).
