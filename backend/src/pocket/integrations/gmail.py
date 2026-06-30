"""Read-only Gmail provider.

Implements GmailProvider.search using the Gmail API with a **read-only** scope
(`gmail.readonly`) — it can search and summarize, but cannot send or modify mail. This is a
separate, least-privilege OAuth client from any other Gmail connection.

Auth uses an authorized-user token JSON (produced once by scripts/gmail-authorize.py, which
runs the OAuth installed-app flow). The `google-*` packages are optional deps, imported
lazily so the app/tests run fully mocked without them. Activation is gated: it needs the
user's own OAuth client + token, provisioned with approval.

Design references: DESIGN.md §10. Default search window is short; the backend summarizes
candidates before any deeper action, and broad searches/drafts are pin_required (policy).
"""

from __future__ import annotations

from typing import Any

from pocket.core.config import Settings, get_settings
from pocket.integrations.base import EmailSummary

# Read-only: no send, no modify. This is the entire requested scope.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GoogleGmail:
    name = "google"

    def __init__(self, settings: Settings | None = None, service: Any | None = None) -> None:
        self._settings = settings or get_settings()
        self._service = service  # injectable for tests; built lazily otherwise

    def search(self, query: str, window_days: int) -> list[EmailSummary]:
        svc = self._service or self._build_service()
        q = f"{query} newer_than:{max(1, window_days)}d"
        listing = (
            svc.users()
            .messages()
            .list(userId="me", q=q, maxResults=self._settings.gmail_max_results)
            .execute()
        )
        results: list[EmailSummary] = []
        for ref in listing.get("messages", []):
            msg = (
                svc.users()
                .messages()
                .get(
                    userId="me",
                    id=ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject"],
                )
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            results.append(
                EmailSummary(
                    thread_id=str(msg.get("threadId", ref["id"])),
                    sender=headers.get("From", ""),
                    subject=headers.get("Subject", ""),
                    gist=msg.get("snippet", ""),
                )
            )
        return results

    def _build_service(self) -> Any:
        # Import via importlib with Any typing so this type-checks the same whether or not the
        # optional google packages are installed (the partial stubs otherwise trip strict mypy).
        import importlib

        credentials_mod: Any = importlib.import_module("google.oauth2.credentials")
        requests_mod: Any = importlib.import_module("google.auth.transport.requests")
        discovery_mod: Any = importlib.import_module("googleapiclient.discovery")

        creds = credentials_mod.Credentials.from_authorized_user_file(
            self._settings.gmail_token_path, SCOPES
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(requests_mod.Request())
        self._service = discovery_mod.build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service
