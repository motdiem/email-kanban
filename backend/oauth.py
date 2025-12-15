import httpx
from urllib.parse import urlencode
from typing import Optional
from config import get_settings

settings = get_settings()


class OAuthProvider:
    """Base OAuth provider class."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_auth_url(self, state: str, scopes: list) -> str:
        raise NotImplementedError

    async def exchange_code(self, code: str) -> dict:
        raise NotImplementedError

    async def refresh_token(self, refresh_token: str) -> dict:
        raise NotImplementedError


class MicrosoftOAuth(OAuthProvider):
    """Microsoft OAuth provider."""

    AUTH_URL = "https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize"
    TOKEN_URL = "https://login.microsoftonline.com/organizations/oauth2/v2.0/token"
    SCOPES = ["Mail.Read", "Mail.ReadWrite", "Mail.Read.Shared", "Mail.ReadWrite.Shared", "offline_access"]

    def get_auth_url(self, state: str, scopes: list = None) -> str:
        scopes = scopes or self.SCOPES
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "response_mode": "query"
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            return response.json()


class GoogleOAuth(OAuthProvider):
    """Google OAuth provider."""

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def get_auth_url(self, state: str, scopes: list = None) -> str:
        scopes = scopes or self.SCOPES
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            return response.json()


class TickTickOAuth(OAuthProvider):
    """TickTick OAuth provider."""

    AUTH_URL = "https://ticktick.com/oauth/authorize"
    TOKEN_URL = "https://ticktick.com/oauth/token"
    SCOPES = ["tasks:read", "tasks:write"]

    def get_auth_url(self, state: str, scopes: list = None) -> str:
        scopes = scopes or self.SCOPES
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            return response.json()


def get_oauth_provider(provider: str) -> Optional[OAuthProvider]:
    """Get OAuth provider instance."""
    redirect_uri = f"{settings.base_url}/auth/callback/{provider}"

    if provider in ("office365", "office365-shared"):
        return MicrosoftOAuth(
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            redirect_uri=redirect_uri
        )
    elif provider == "gmail":
        return GoogleOAuth(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=redirect_uri
        )
    elif provider == "ticktick":
        return TickTickOAuth(
            client_id=settings.ticktick_client_id,
            client_secret=settings.ticktick_client_secret,
            redirect_uri=redirect_uri
        )
    return None
