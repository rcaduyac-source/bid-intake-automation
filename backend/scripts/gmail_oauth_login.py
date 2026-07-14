#!/usr/bin/env python3
"""One-time Gmail user OAuth login. Saves a refresh token for the backend poller.

Prerequisites (Google Cloud Console — you can do this without Workspace admin):
  1. Enable Gmail API
  2. APIs & Services → OAuth consent screen
       - User type: External
       - Publishing status: Testing
       - Add your mailbox as a Test user
  3. APIs & Services → Credentials → Create Credentials → OAuth client ID
       - Application type: Desktop app
       - Download JSON → save as secrets/gmail_oauth_client.json

Usage (from backend/, on your Mac — needs a browser):
  uv run python scripts/gmail_oauth_login.py

Sign in as the inbox you want to poll (e.g. rcaduyac@byrdsonservices.com).
Then restart Docker backend with GMAIL_ENABLED=true.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing config from src/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from config import get_settings  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main() -> None:
    settings = get_settings()
    client_secrets = Path(settings.gmail_oauth_client_secrets)
    token_path = Path(settings.gmail_token_path)

    if not client_secrets.exists():
        raise SystemExit(
            f"Missing OAuth client secrets at {client_secrets}\n"
            "Create a Desktop OAuth client in Google Cloud and download the JSON there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    if not creds.refresh_token:
        raise SystemExit(
            "No refresh_token returned. Revoke prior access at "
            "https://myaccount.google.com/permissions then run this script again."
        )

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    print(f"Saved refresh token → {token_path.resolve()}")
    print("Set GMAIL_ENABLED=true and restart the backend.")


if __name__ == "__main__":
    main()
