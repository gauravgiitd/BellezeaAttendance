#!/usr/bin/env python3
"""One-time OAuth setup for election backup Google Sheets.

Sign in as bellezea.elections@gmail.com and paste the printed refresh token into
.env.local as GOOGLE_DRIVE_REFRESH_TOKEN.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PREFERRED_PYTHON = ROOT / ".venv" / "bin" / "python3.14"
DEFAULT_OAUTH_PORT = 8765
DEFAULT_OAUTH_HOST = "127.0.0.1"


def ensure_supported_python() -> None:
    try:
        import google_auth_oauthlib  # noqa: F401
        return
    except ImportError:
        pass

    if PREFERRED_PYTHON.is_file() and Path(sys.executable).resolve() != PREFERRED_PYTHON.resolve():
        os.execv(str(PREFERRED_PYTHON), [str(PREFERRED_PYTHON), *sys.argv])

    print(
        "Install dependencies with the same Python that runs this script:\n"
        f"  {sys.executable} -m pip install google-auth-oauthlib\n"
        "Or run:\n"
        "  .venv/bin/python3.14 scripts/authorize_google_drive_backup.py",
        file=sys.stderr,
    )
    raise SystemExit(1)


ensure_supported_python()

ENV_LOCAL = ROOT / ".env.local"
if ENV_LOCAL.is_file():
    for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from backend.app.integrations.election_backup_sheet.sheets_client import SCOPES, oauth_client_credentials


def resolve_oauth_port() -> int:
    configured = os.environ.get("GOOGLE_OAUTH_LOCAL_PORT", "").strip()
    port = int(configured) if configured else DEFAULT_OAUTH_PORT
    host = os.environ.get("GOOGLE_OAUTH_LOCAL_HOST", DEFAULT_OAUTH_HOST).strip() or DEFAULT_OAUTH_HOST
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            raise RuntimeError(
                f"Port {port} on {host} is already in use. Free it with:\n"
                f"  lsof -i :{port}\n"
                f"  kill <PID>\n"
                "Or choose another port:\n"
                f"  GOOGLE_OAUTH_LOCAL_PORT=8766 .venv/bin/python3.14 scripts/authorize_google_drive_backup.py"
            ) from exc
    return port


def main() -> int:
    client_id, client_secret = oauth_client_credentials()
    if not client_id or not client_secret:
        print(
            "Set OAuth client credentials in .env.local first.\n"
            "Recommended (Desktop OAuth client):\n"
            "  GOOGLE_DRIVE_OAUTH_CLIENT_ID=...\n"
            "  GOOGLE_DRIVE_OAUTH_CLIENT_SECRET=...\n"
            "Fallback:\n"
            "  GOOGLE_CLIENT_ID=...\n"
            "  GOOGLE_CLIENT_SECRET=...",
            file=sys.stderr,
        )
        return 1

    using_drive_client = bool(os.environ.get("GOOGLE_DRIVE_OAUTH_CLIENT_ID", "").strip())
    host = os.environ.get("GOOGLE_OAUTH_LOCAL_HOST", DEFAULT_OAUTH_HOST).strip() or DEFAULT_OAUTH_HOST

    try:
        port = resolve_oauth_port()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    redirect_uri = f"http://{host}:{port}"
    localhost_alias = f"http://localhost:{port}"

    print("Google OAuth setup for election backup sheets")
    print("============================================")
    print(f"OAuth client ID: {client_id}")
    print(f"Redirect URI:    {redirect_uri}")
    print()
    if not using_drive_client:
        print("Warning: using GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET.")
        print("Officer login uses a Web OAuth client; that often fails for this localhost flow.")
        print("Create a separate OAuth client of type Desktop app and set:")
        print("  GOOGLE_DRIVE_OAUTH_CLIENT_ID")
        print("  GOOGLE_DRIVE_OAUTH_CLIENT_SECRET")
        print()
    print("In Google Cloud Console:")
    print("  APIs & Services → Credentials")
    print("  Open the OAuth client whose Client ID matches the value above")
    print("  Recommended client type: Desktop app")
    print("  Authorized redirect URIs → add BOTH of these if Google allows both:")
    print(f"    {redirect_uri}")
    print(f"    {localhost_alias}")
    print()
    print("Also check OAuth consent screen → Test users includes bellezea.elections@gmail.com")
    print()
    input("Press Enter after saving the redirect URI(s) on that exact OAuth client... ")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            f"Install google-auth-oauthlib for {sys.executable}:\n"
            f"  {sys.executable} -m pip install google-auth-oauthlib",
            file=sys.stderr,
        )
        return 1

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri, localhost_alias, "http://127.0.0.1", "http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    print(f"\nOAuth will use redirect URI: {redirect_uri}")
    print(f"Register that URI on OAuth client: {client_id}\n")
    print("Opening browser. Sign in as bellezea.elections@gmail.com\n")
    credentials = flow.run_local_server(
        host=host,
        port=port,
        redirect_uri_trailing_slash=False,
        authorization_prompt_message=f"Opening browser for OAuth. Redirect URI: {redirect_uri}",
        prompt="consent",
        access_type="offline",
        open_browser=True,
    )

    if not credentials.refresh_token:
        print(
            "Google did not return a refresh token. Remove prior app access at "
            "https://myaccount.google.com/permissions and run this script again.",
            file=sys.stderr,
        )
        return 1

    print("\nAdd these lines to .env.local:\n")
    if using_drive_client:
        print(f'GOOGLE_DRIVE_OAUTH_CLIENT_ID="{client_id}"')
        print(f'GOOGLE_DRIVE_OAUTH_CLIENT_SECRET="{client_secret}"')
    print(f'GOOGLE_DRIVE_REFRESH_TOKEN="{credentials.refresh_token}"')
    print("\nThen restart ./scripts/start_local_api.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
