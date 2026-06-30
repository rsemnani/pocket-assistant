#!/usr/bin/env python3
"""One-time Gmail authorization for the read-only provider.

Runs the OAuth installed-app flow against YOUR Google Cloud OAuth client and writes an
authorized-user token JSON the backend can refresh non-interactively. Read-only scope only.

Prereqs:
  1. In Google Cloud Console: create a project, enable the Gmail API, configure an OAuth
     consent screen (External; add yourself as a test user), and create an OAuth client of
     type "Desktop app". Download its client secret JSON.
  2. pip install google-auth-oauthlib google-api-python-client

Usage:
  python scripts/gmail-authorize.py --client-secret client_secret.json --out token.json

Then copy token.json to the mini at the path GMAIL_TOKEN_PATH points to (default
deploy/_gmail/token.json) and set GMAIL_PROVIDER=google.
"""

from __future__ import annotations

import argparse

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize read-only Gmail access.")
    parser.add_argument("--client-secret", required=True, help="OAuth client secret JSON path")
    parser.add_argument("--out", default="token.json", help="Output token path")
    args = parser.parse_args()

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())
    print(f"Wrote {args.out} (read-only Gmail token). Keep it secret; never commit it.")


if __name__ == "__main__":
    main()
