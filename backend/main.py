from fastapi import FastAPI, HTTPException, Depends, Query, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt, JWTError
import secrets
import uuid

from config import get_settings
from database import (
    init_db, create_account, get_account, get_all_accounts,
    update_account, delete_account, upsert_items, get_items,
    delete_item, clear_account_items, get_last_sync
)
from oauth import get_oauth_provider
from providers import (
    MicrosoftProvider, GmailProvider, TickTickProvider,
    YahooProvider, ICloudProvider, get_start_of_week_paris
)

settings = get_settings()

app = FastAPI(title="Email Kanban API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store OAuth states temporarily (in production, use Redis)
oauth_states = {}


# ============================================================
# Auth Models
# ============================================================
class LoginRequest(BaseModel):
    pin: str


class AccountCreate(BaseModel):
    name: str
    provider: str
    color: str = "#0078d4"
    shared_mailbox: Optional[str] = None
    gmail_account_number: Optional[int] = 0
    # For Yahoo (email needed for IMAP login with OAuth token)
    yahoo_email: Optional[str] = None
    # For iCloud (uses app-specific password instead of OAuth)
    icloud_email: Optional[str] = None
    icloud_app_password: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    shared_mailbox: Optional[str] = None
    gmail_account_number: Optional[int] = None
    icloud_email: Optional[str] = None
    icloud_app_password: Optional[str] = None


# ============================================================
# Auth Helpers
# ============================================================
def create_session_token(data: dict, expires_delta: timedelta = timedelta(days=30)) -> str:
    """Create a JWT session token."""
    expire = datetime.utcnow() + expires_delta
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.app_secret_key, algorithm="HS256")


def verify_session_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT session token."""
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


async def get_current_session(session: str = Cookie(None)):
    """Dependency to verify session."""
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = verify_session_token(session)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid session")

    return payload


# ============================================================
# Startup
# ============================================================
@app.on_event("startup")
async def startup():
    await init_db()


# ============================================================
# Auth Routes
# ============================================================
@app.post("/auth/login")
async def login(request: LoginRequest, response: Response):
    """Login with PIN."""
    if request.pin != settings.app_pin:
        raise HTTPException(status_code=401, detail="Invalid PIN")

    token = create_session_token({"authenticated": True})
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,  # 30 days
        samesite="lax"
    )
    return {"status": "ok"}


@app.post("/auth/logout")
async def logout(response: Response):
    """Logout."""
    response.delete_cookie("session")
    return {"status": "ok"}


@app.get("/auth/check")
async def check_auth(session: dict = Depends(get_current_session)):
    """Check if authenticated."""
    return {"authenticated": True}


# ============================================================
# OAuth Routes
# ============================================================
@app.get("/auth/authorize/{provider}")
async def authorize(provider: str, account_id: str = Query(...), session: dict = Depends(get_current_session)):
    """Start OAuth flow."""
    oauth = get_oauth_provider(provider)
    if not oauth:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    state = secrets.token_urlsafe(32)
    oauth_states[state] = {"account_id": account_id, "provider": provider}

    auth_url = oauth.get_auth_url(state)
    return {"auth_url": auth_url}


@app.get("/auth/callback/{provider}")
async def oauth_callback(provider: str, code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    """OAuth callback handler."""
    if error:
        return RedirectResponse(f"{settings.frontend_url}?error={error}")

    if not state or state not in oauth_states:
        return RedirectResponse(f"{settings.frontend_url}?error=invalid_state")

    state_data = oauth_states.pop(state)
    account_id = state_data["account_id"]

    oauth = get_oauth_provider(provider)
    if not oauth:
        return RedirectResponse(f"{settings.frontend_url}?error=unknown_provider")

    try:
        tokens = await oauth.exchange_code(code)

        # Get existing account
        account = await get_account(account_id)
        if not account:
            return RedirectResponse(f"{settings.frontend_url}?error=account_not_found")

        # Update account with tokens
        config = account.get("config", {})
        config["access_token"] = tokens.get("access_token")
        config["refresh_token"] = tokens.get("refresh_token")
        config["expires_at"] = datetime.utcnow().timestamp() + tokens.get("expires_in", 3600)

        await update_account(account_id, config=config)

        return RedirectResponse(f"{settings.frontend_url}?oauth=success&account={account_id}")

    except Exception as e:
        return RedirectResponse(f"{settings.frontend_url}?error={str(e)}")


# ============================================================
# Account Routes
# ============================================================
@app.get("/accounts")
async def list_accounts(session: dict = Depends(get_current_session)):
    """List all accounts."""
    accounts = await get_all_accounts()
    return {"accounts": accounts}


@app.post("/accounts")
async def add_account(account: AccountCreate, session: dict = Depends(get_current_session)):
    """Create a new account."""
    account_id = f"acc_{uuid.uuid4().hex[:9]}"

    config = {
        "shared_mailbox": account.shared_mailbox,
        "gmail_account_number": account.gmail_account_number
    }

    email = ""

    # Yahoo needs email for IMAP login with OAuth token
    if account.provider == "yahoo":
        if not account.yahoo_email:
            raise HTTPException(
                status_code=400,
                detail="Yahoo requires email address"
            )
        email = account.yahoo_email

    # iCloud uses app-specific password instead of OAuth
    if account.provider == "icloud":
        if not account.icloud_email or not account.icloud_app_password:
            raise HTTPException(
                status_code=400,
                detail="iCloud requires email and app-specific password"
            )
        config["icloud_email"] = account.icloud_email
        config["icloud_app_password"] = account.icloud_app_password
        email = account.icloud_email

    new_account = await create_account(
        id=account_id,
        name=account.name,
        provider=account.provider,
        email=email,
        color=account.color,
        config=config
    )

    return {"account": new_account}


@app.get("/accounts/{account_id}")
async def get_account_details(account_id: str, session: dict = Depends(get_current_session)):
    """Get account details."""
    account = await get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Don't return sensitive tokens
    safe_account = {
        "id": account["id"],
        "name": account["name"],
        "provider": account["provider"],
        "email": account.get("email"),
        "color": account.get("color"),
        "has_token": bool(account.get("config", {}).get("access_token")),
        "shared_mailbox": account.get("config", {}).get("shared_mailbox"),
        "gmail_account_number": account.get("config", {}).get("gmail_account_number", 0)
    }
    return {"account": safe_account}


@app.patch("/accounts/{account_id}")
async def update_account_details(
    account_id: str,
    updates: AccountUpdate,
    session: dict = Depends(get_current_session)
):
    """Update account details."""
    account = await get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    update_data = {}
    config_updates = {}

    if updates.name:
        update_data["name"] = updates.name
    if updates.color:
        update_data["color"] = updates.color
    if updates.shared_mailbox is not None:
        config_updates["shared_mailbox"] = updates.shared_mailbox
    if updates.gmail_account_number is not None:
        config_updates["gmail_account_number"] = updates.gmail_account_number

    if config_updates:
        config = account.get("config", {})
        config.update(config_updates)
        update_data["config"] = config

    await update_account(account_id, **update_data)
    return {"status": "ok"}


@app.delete("/accounts/{account_id}")
async def remove_account(account_id: str, session: dict = Depends(get_current_session)):
    """Delete an account."""
    await delete_account(account_id)
    return {"status": "ok"}


# ============================================================
# Token Refresh Helper
# ============================================================
async def get_valid_token(account: dict) -> str:
    """Get a valid access token, refreshing if necessary."""
    config = account.get("config", {})
    access_token = config.get("access_token")
    refresh_token = config.get("refresh_token")
    expires_at = config.get("expires_at", 0)

    if not access_token:
        raise HTTPException(status_code=401, detail="Account not authorized")

    # Check if token is expired (with 5 min buffer)
    if datetime.utcnow().timestamp() > expires_at - 300:
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Token expired, please re-authorize")

        oauth = get_oauth_provider(account["provider"])
        if not oauth:
            raise HTTPException(status_code=400, detail="Unknown provider")

        try:
            tokens = await oauth.refresh_token(refresh_token)
            config["access_token"] = tokens.get("access_token")
            if tokens.get("refresh_token"):
                config["refresh_token"] = tokens["refresh_token"]
            config["expires_at"] = datetime.utcnow().timestamp() + tokens.get("expires_in", 3600)

            await update_account(account["id"], config=config)
            access_token = config["access_token"]
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")

    return access_token


# ============================================================
# Email/Task Routes
# ============================================================
@app.get("/accounts/{account_id}/items")
async def get_account_items(
    account_id: str,
    force_refresh: bool = False,
    session: dict = Depends(get_current_session)
):
    """Get emails or tasks for an account."""
    account = await get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    provider = account["provider"]
    config = account.get("config", {})

    # Check cache first (unless force refresh)
    item_type = "task" if provider == "ticktick" else "email"
    last_sync = await get_last_sync(account_id, item_type)

    # Use cache if synced within last 5 minutes
    if not force_refresh and last_sync and (datetime.utcnow() - last_sync).seconds < 300:
        items = await get_items(account_id, item_type)
        return {"items": items, "cached": True, "last_sync": last_sync.isoformat()}

    # Fetch fresh data
    try:
        start_date = get_start_of_week_paris()

        # iCloud doesn't use OAuth - uses app-specific password
        if provider == "icloud":
            icloud_email = config.get("icloud_email")
            icloud_password = config.get("icloud_app_password")
            if not icloud_email or not icloud_password:
                raise HTTPException(status_code=401, detail="iCloud credentials not configured")
            api = ICloudProvider(icloud_email, icloud_password)
            items = await api.get_emails(start_date)
        else:
            # OAuth-based providers
            access_token = await get_valid_token(account)

            if provider in ("office365", "office365-shared"):
                api = MicrosoftProvider(access_token)
                items = await api.get_emails(start_date, config.get("shared_mailbox"))
            elif provider == "gmail":
                api = GmailProvider(access_token)
                items = await api.get_emails(start_date, config.get("gmail_account_number", 0))
            elif provider == "yahoo":
                # Yahoo needs email address for IMAP login
                email_address = account.get("email", "")
                if not email_address:
                    raise HTTPException(status_code=401, detail="Yahoo email address not found")
                api = YahooProvider(access_token, email_address)
                items = await api.get_emails(start_date)
            elif provider == "ticktick":
                api = TickTickProvider(access_token)
                items = await api.get_tasks()
            else:
                raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

        # Update cache
        await clear_account_items(account_id, item_type)
        await upsert_items(account_id, item_type, items)

        return {"items": items, "cached": False, "last_sync": datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        # Try to return cached data on error
        items = await get_items(account_id, item_type)
        if items:
            return {"items": items, "cached": True, "error": str(e)}
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accounts/{account_id}/sync")
async def sync_account(account_id: str, session: dict = Depends(get_current_session)):
    """Force sync an account."""
    return await get_account_items(account_id, force_refresh=True, session=session)


# ============================================================
# Email Actions
# ============================================================
@app.post("/accounts/{account_id}/emails/{email_id}/archive")
async def archive_email(account_id: str, email_id: str, session: dict = Depends(get_current_session)):
    """Archive an email."""
    account = await get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    access_token = await get_valid_token(account)
    config = account.get("config", {})

    if account["provider"] in ("office365", "office365-shared"):
        api = MicrosoftProvider(access_token)
        await api.archive_email(email_id, config.get("shared_mailbox"))
    elif account["provider"] == "gmail":
        api = GmailProvider(access_token)
        await api.archive_email(email_id)
    else:
        raise HTTPException(status_code=400, detail="Provider does not support archive")

    # Remove from cache
    await delete_item(email_id)
    return {"status": "ok"}


@app.post("/accounts/{account_id}/emails/{email_id}/star")
async def toggle_email_star(
    account_id: str,
    email_id: str,
    starred: bool = Query(...),
    session: dict = Depends(get_current_session)
):
    """Toggle email star/flag."""
    account = await get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    access_token = await get_valid_token(account)
    config = account.get("config", {})

    if account["provider"] in ("office365", "office365-shared"):
        api = MicrosoftProvider(access_token)
        await api.toggle_flag(email_id, starred, config.get("shared_mailbox"))
    elif account["provider"] == "gmail":
        api = GmailProvider(access_token)
        await api.toggle_star(email_id, starred)
    else:
        raise HTTPException(status_code=400, detail="Provider does not support star")

    return {"status": "ok"}


# ============================================================
# Task Actions
# ============================================================
@app.post("/accounts/{account_id}/tasks/{task_id}/complete")
async def toggle_task_complete(
    account_id: str,
    task_id: str,
    project_id: str = Query(...),
    completed: bool = Query(...),
    session: dict = Depends(get_current_session)
):
    """Toggle task completion."""
    account = await get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account["provider"] != "ticktick":
        raise HTTPException(status_code=400, detail="Not a task provider")

    access_token = await get_valid_token(account)
    api = TickTickProvider(access_token)

    if completed:
        await api.complete_task(project_id, task_id)
    else:
        await api.uncomplete_task(project_id, task_id)

    return {"status": "ok"}


# ============================================================
# Public Config (no auth required)
# ============================================================
@app.get("/config")
async def get_public_config():
    """Get public OAuth configuration (client IDs only, no secrets)."""
    return {
        "microsoft": {
            "clientId": settings.microsoft_client_id,
            "authority": "https://login.microsoftonline.com/organizations",
            "scopes": ["Mail.Read", "Mail.ReadWrite", "Mail.Read.Shared", "Mail.ReadWrite.Shared"]
        },
        "google": {
            "clientId": settings.google_client_id,
            "scopes": ["https://www.googleapis.com/auth/gmail.modify"]
        },
        "yahoo": {
            "clientId": settings.yahoo_client_id,
            "authUrl": "https://api.login.yahoo.com/oauth2/request_auth",
            "scopes": ["mail-r"]
        },
        "ticktick": {
            "clientId": settings.ticktick_client_id,
            "authUrl": "https://ticktick.com/oauth/authorize",
            "scopes": ["tasks:read", "tasks:write"]
        },
        "icloud": {
            "requiresAppPassword": True,
            "helpUrl": "https://support.apple.com/en-us/HT204397"
        }
    }


# ============================================================
# Health Check
# ============================================================
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
