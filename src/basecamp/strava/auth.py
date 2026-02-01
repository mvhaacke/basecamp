import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from stravalib import Client

from basecamp.config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REDIRECT_URI
from basecamp.database import get_session
from basecamp.models import Token


def _get_stored_token() -> Token | None:
    with get_session() as session:
        return session.query(Token).order_by(Token.updated_at.desc()).first()


def _save_token(access_token: str, refresh_token: str, expires_at: int, athlete_id: int | None = None):
    with get_session() as session:
        token = session.query(Token).first()
        if token:
            token.access_token = access_token
            token.refresh_token = refresh_token
            token.expires_at = expires_at
            if athlete_id:
                token.athlete_id = athlete_id
        else:
            token = Token(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                athlete_id=athlete_id,
            )
            session.add(token)
        session.commit()


def get_authenticated_client() -> Client:
    """Return a stravalib Client with a valid access token, refreshing if needed."""
    token = _get_stored_token()
    if not token:
        raise RuntimeError("Not authenticated. Run 'basecamp auth' first.")

    client = Client(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
    )

    if token.expires_at < time.time():
        refresh_response = client.refresh_access_token(
            client_id=int(STRAVA_CLIENT_ID),
            client_secret=STRAVA_CLIENT_SECRET,
            refresh_token=token.refresh_token,
        )
        _save_token(
            access_token=refresh_response["access_token"],
            refresh_token=refresh_response["refresh_token"],
            expires_at=refresh_response["expires_at"],
        )
        client.access_token = refresh_response["access_token"]
        client.refresh_token = refresh_response["refresh_token"]

    return client


def authenticate():
    """Run the full OAuth2 flow: open browser, catch callback, store tokens."""
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        raise RuntimeError(
            "STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET must be set in .env\n"
            "Create a Strava API app at https://www.strava.com/settings/api"
        )

    client = Client()
    auth_url = client.authorization_url(
        client_id=int(STRAVA_CLIENT_ID),
        redirect_uri=STRAVA_REDIRECT_URI,
        scope=["activity:read_all"],
    )

    # Capture the authorization code via a local HTTP server
    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            query = parse_qs(urlparse(self.path).query)
            auth_code = query.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authenticated! You can close this tab.</h1>")

        def log_message(self, format, *args):
            pass  # suppress server logs

    server = HTTPServer(("localhost", 8000), CallbackHandler)

    print(f"Opening browser for Strava authorization...")
    webbrowser.open(auth_url)
    print("Waiting for callback on http://localhost:8000 ...")

    server.handle_request()  # handle exactly one request

    if not auth_code:
        raise RuntimeError("Failed to receive authorization code from Strava.")

    token_response = client.exchange_code_for_token(
        client_id=int(STRAVA_CLIENT_ID),
        client_secret=STRAVA_CLIENT_SECRET,
        code=auth_code,
    )

    athlete_id = token_response.get("athlete", {}).get("id") if isinstance(token_response.get("athlete"), dict) else None

    _save_token(
        access_token=token_response["access_token"],
        refresh_token=token_response["refresh_token"],
        expires_at=token_response["expires_at"],
        athlete_id=athlete_id,
    )

    return token_response
