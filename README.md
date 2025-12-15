# Email & Task Kanban - Multi-Account Dashboard

A web application that displays emails and tasks from multiple providers (Microsoft Office 365, Gmail, TickTick) in a Kanban-style board. View all your inboxes and tasks at a glance, organized by day of the week.

## Features

### Multi-Provider Support
- **Microsoft Office 365** - Personal, work, and school accounts
- **Office 365 Shared Mailboxes** - Access shared organizational mailboxes
- **Gmail / Google Workspace** - Personal and work Google accounts
- **TickTick Tasks** - View and manage tasks from TickTick

### Views
- **Home View**: See today's emails and tasks from all accounts side-by-side
- **Weekly View**: Click any account to see emails/tasks organized by day (Monday → Sunday)
  - Email accounts: Shows emails received on each day
  - Task accounts: Past days show completed tasks, today shows due/overdue, future days show planned tasks

### Actions
- **Star/Flag**: Toggle star (Gmail) or flag (Outlook) status
- **Archive**: Move to archive folder (Outlook) or remove from inbox (Gmail)
- **Complete Tasks**: Toggle task completion status (TickTick)
- **Open**: Click any item to open it in its native web app

### Customization
- **Color Picker**: Assign custom colors to each account
- **Reorder Accounts**: Drag-and-drop columns or use settings to reorder
- **Export/Import**: Backup and restore your configuration

---

## Deployment Options

### Option 1: Client-Only (Simple)

Best for: Local/personal use, quick setup

```
┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│  Gmail/     │
│  (Frontend) │◀────│  Outlook/   │
│             │     │  TickTick   │
└─────────────┘     └─────────────┘
```

- Single HTML file
- OAuth tokens stored in browser localStorage
- No server required (just a static file server)
- ⚠️ TickTick client secret exposed in browser

### Option 2: With Backend (Secure)

Best for: Hosted deployment, multiple users, security

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│   FastAPI   │────▶│  Gmail/     │
│  (Frontend) │◀────│   Backend   │◀────│  Outlook/   │
└─────────────┘     └─────────────┘     │  TickTick   │
                          │             └─────────────┘
                          ▼
                    ┌───────────┐
                    │  SQLite   │
                    │  (cache)  │
                    └───────────┘
```

- PIN-protected access
- OAuth tokens encrypted server-side
- 5-minute cache for faster loads
- Docker-ready for easy deployment

---

## Quick Start

### Client-Only Mode

```bash
# 1. Setup configuration
cp config.example.js config.js
# Edit config.js with your OAuth client IDs

# 2. Serve the application
python -m http.server 8000

# 3. Open in browser
open http://localhost:8000/index.html
```

### Backend Mode

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with your OAuth credentials

# 2. Start backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8001

# 3. Serve frontend (new terminal)
cd ..
python -m http.server 8000

# 4. Open in browser
open http://localhost:8000/index-backend.html
```

### Docker Deployment

```bash
# Setup and run
cp .env.example .env
# Edit .env with your credentials
docker-compose up -d

# Open in browser
open http://localhost:8000
```

---

## Project Structure

```
email-kanban/
├── index.html              # Client-only frontend (no backend needed)
├── index-backend.html      # Backend-enabled frontend
├── config.example.js       # OAuth config template (copy to config.js)
├── README.md               # This documentation
│
├── backend/                # FastAPI backend
│   ├── main.py             # API routes and app entry point
│   ├── config.py           # Environment configuration
│   ├── database.py         # SQLite with encrypted token storage
│   ├── oauth.py            # OAuth providers (Microsoft, Google, TickTick)
│   ├── providers.py        # Email/task API clients
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile          # Backend container config
│   ├── .env.example        # Environment template
│   └── README.md           # Backend-specific docs
│
├── docker-compose.yml      # Full-stack deployment
├── nginx.conf              # Reverse proxy config
└── .env.example            # Root environment template
```

---

## Configuration

### Environment Variables (.env)

```bash
# Security
APP_SECRET_KEY=generate-with-python-c-import-secrets-print-secrets.token_urlsafe-32
APP_PIN=1234                          # Access PIN for backend mode

# URLs (update for production)
BASE_URL=http://localhost:8001        # Backend URL
FRONTEND_URL=http://localhost:8000    # Frontend URL

# Microsoft OAuth
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# TickTick OAuth
TICKTICK_CLIENT_ID=your-client-id
TICKTICK_CLIENT_SECRET=your-client-secret
```

### OAuth Redirect URIs

| Provider | Client-Only Mode | Backend Mode |
|----------|------------------|--------------|
| Microsoft | `http://localhost:8000/index.html` | `http://localhost:8001/auth/callback/office365` |
| Google | `http://localhost:8000/index.html` | `http://localhost:8001/auth/callback/gmail` |
| TickTick | `http://localhost:8000/index.html` | `http://localhost:8001/auth/callback/ticktick` |

---

## Provider Setup

### Microsoft Office 365

1. Go to [Azure Portal](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Click **New registration**
3. Configure:
   - **Name**: `Email Kanban`
   - **Supported account types**: Accounts in any organizational directory (Multitenant)
   - **Redirect URI**: See table above (Platform: SPA for client-only, Web for backend)
4. Copy **Application (client) ID**
5. Go to **Certificates & secrets** → Create new client secret (backend mode only)
6. Go to **API permissions** → Add:
   - `Mail.Read`
   - `Mail.ReadWrite`
   - `Mail.Read.Shared`
   - `Mail.ReadWrite.Shared`
   - `offline_access` (backend mode)
7. Click **Grant admin consent**

### Gmail / Google Workspace

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable **Gmail API**
3. Go to **OAuth consent screen**:
   - Select External (or Internal for Workspace)
   - Add scope: `https://www.googleapis.com/auth/gmail.modify`
   - Add test users (for External apps)
4. Go to **Credentials** → Create **OAuth client ID**:
   - Type: Web application
   - Authorized origins: `http://localhost:8000`
   - Authorized redirect URIs: See table above
5. Copy **Client ID** and **Client Secret**

### TickTick

1. Go to [TickTick Developer Portal](https://developer.ticktick.com/manage)
2. Create new app
3. Set **OAuth Redirect URL**: See table above
4. Copy **Client ID** and **Client Secret**

---

## Code Architecture

### Frontend (index.html / index-backend.html)

```
┌─────────────────────────────────────────────────────────────┐
│ CONFIGURATION                                               │
│ - OAuth client IDs and scopes                               │
│ - Color palette, provider icons                             │
├─────────────────────────────────────────────────────────────┤
│ STATE                                                       │
│ - accounts[] - List of configured accounts                  │
│ - emailCache{} / taskCache{} - Cached data by account       │
│ - currentView - 'home' or 'account'                         │
├─────────────────────────────────────────────────────────────┤
│ INITIALIZATION                                              │
│ - Load accounts from localStorage (client) or API (backend) │
│ - Initialize OAuth libraries                                │
├─────────────────────────────────────────────────────────────┤
│ DATE HELPERS                                                │
│ - Paris timezone conversions                                │
│ - Week/day calculations (getStartOfWeek, getDateStr)        │
├─────────────────────────────────────────────────────────────┤
│ AUTHENTICATION                                              │
│ - Client: Direct OAuth with MSAL/Google                     │
│ - Backend: PIN login + OAuth via backend proxy              │
├─────────────────────────────────────────────────────────────┤
│ DATA FETCHING                                               │
│ - Client: Direct API calls to providers                     │
│ - Backend: /api/accounts/{id}/items                         │
├─────────────────────────────────────────────────────────────┤
│ VIEW RENDERING                                              │
│ - loadHomeView() - Today's items per account                │
│ - loadAccountView() - Weekly view for one account           │
│ - createCard() - Email/task card component                  │
├─────────────────────────────────────────────────────────────┤
│ ACTIONS                                                     │
│ - archiveEmail(), toggleStar(), toggleTaskComplete()        │
├─────────────────────────────────────────────────────────────┤
│ MODALS                                                      │
│ - Add Account, Account Setup, Settings, Color Picker        │
└─────────────────────────────────────────────────────────────┘
```

### Backend (backend/)

```
┌─────────────────────────────────────────────────────────────┐
│ main.py - FastAPI Application                               │
├─────────────────────────────────────────────────────────────┤
│ AUTH ROUTES                                                 │
│ - POST /auth/login - PIN authentication                     │
│ - POST /auth/logout - Clear session                         │
│ - GET /auth/authorize/{provider} - Start OAuth              │
│ - GET /auth/callback/{provider} - OAuth callback            │
├─────────────────────────────────────────────────────────────┤
│ ACCOUNT ROUTES                                              │
│ - GET /accounts - List all accounts                         │
│ - POST /accounts - Create account                           │
│ - GET /accounts/{id} - Get account details                  │
│ - PATCH /accounts/{id} - Update account                     │
│ - DELETE /accounts/{id} - Delete account                    │
├─────────────────────────────────────────────────────────────┤
│ DATA ROUTES                                                 │
│ - GET /accounts/{id}/items - Get emails/tasks (cached)      │
│ - POST /accounts/{id}/sync - Force refresh                  │
├─────────────────────────────────────────────────────────────┤
│ ACTION ROUTES                                               │
│ - POST /accounts/{id}/emails/{id}/archive                   │
│ - POST /accounts/{id}/emails/{id}/star                      │
│ - POST /accounts/{id}/tasks/{id}/complete                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ database.py - SQLite Storage                                │
├─────────────────────────────────────────────────────────────┤
│ TABLES                                                      │
│ - accounts: id, name, provider, email, color, config (enc)  │
│ - items: id, account_id, type, title, date, data (JSON)     │
├─────────────────────────────────────────────────────────────┤
│ ENCRYPTION                                                  │
│ - Fernet encryption for OAuth tokens                        │
│ - Key derived from APP_SECRET_KEY                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ oauth.py - OAuth Providers                                  │
├─────────────────────────────────────────────────────────────┤
│ PROVIDERS                                                   │
│ - MicrosoftOAuth: Azure AD / Graph API                      │
│ - GoogleOAuth: Google Identity Platform                     │
│ - TickTickOAuth: TickTick Open API                          │
├─────────────────────────────────────────────────────────────┤
│ METHODS                                                     │
│ - get_auth_url(state) - Generate authorization URL          │
│ - exchange_code(code) - Exchange code for tokens            │
│ - refresh_token(token) - Refresh expired tokens             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ providers.py - API Clients                                  │
├─────────────────────────────────────────────────────────────┤
│ PROVIDERS                                                   │
│ - MicrosoftProvider: MS Graph API for emails                │
│ - GmailProvider: Gmail API for emails                       │
│ - TickTickProvider: TickTick API for tasks                  │
├─────────────────────────────────────────────────────────────┤
│ METHODS                                                     │
│ - get_emails(start_date) / get_tasks()                      │
│ - archive_email(id), toggle_star/flag(id)                   │
│ - complete_task(project_id, task_id)                        │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Client-Only Mode:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ localStorage │────▶│   Browser    │────▶│  Provider    │
│  (accounts)  │     │   (OAuth)    │     │    APIs      │
└──────────────┘     └──────────────┘     └──────────────┘

Backend Mode:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Browser    │────▶│   FastAPI    │────▶│  Provider    │
│  (session)   │     │   Backend    │     │    APIs      │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   SQLite     │
                     │ (encrypted)  │
                     └──────────────┘
```

---

## API Reference

### Provider APIs Used

#### Microsoft Graph API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/me/mailFolders/inbox/messages` | GET | Fetch inbox emails |
| `/users/{email}/mailFolders/inbox/messages` | GET | Fetch shared mailbox |
| `/me/messages/{id}/move` | POST | Archive email |
| `/me/messages/{id}` | PATCH | Update flag status |

#### Gmail API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/gmail/v1/users/me/messages` | GET | List message IDs |
| `/gmail/v1/users/me/messages/{id}` | GET | Get message details |
| `/gmail/v1/users/me/messages/{id}/modify` | POST | Archive/star email |

#### TickTick Open API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/open/v1/project` | GET | List all projects |
| `/open/v1/project/{id}/data` | GET | Get project tasks |
| `/open/v1/project/{id}/task/{id}/complete` | POST | Complete task |

---

## Troubleshooting

### OAuth Errors

**"redirect_uri_mismatch"**
- Ensure URL exactly matches what's registered in provider dashboard
- Check http vs https, trailing slashes, port numbers

**"Admin consent required" (Microsoft)**
- Contact IT admin or use personal Microsoft account

**"Access blocked: App not verified" (Google)**
- Add your email as Test User in OAuth consent screen

### Data Issues

**Emails/Tasks not loading**
- Check browser console (F12) for errors
- Verify API permissions are granted
- Try removing and re-adding the account

**Tasks without dates not showing**
- Tasks need a due date to appear in the calendar view
- Tasks without dates are filtered out

**Wrong timezone**
- All dates are converted to Europe/Paris timezone
- Modify `getDateStr()` function to change timezone

### Backend Issues

**"Invalid PIN"**
- Check APP_PIN in .env matches what you're entering

**"Token refresh failed"**
- Token may have been revoked
- Remove account and re-add it

**Database errors**
- Delete `data/kanban.db` and restart
- Ensure `data/` directory is writable

---

## Security Considerations

### Client-Only Mode
- OAuth tokens in localStorage (accessible via browser dev tools)
- TickTick client secret visible in browser
- Best for personal/local use only

### Backend Mode
- Tokens encrypted at rest with Fernet
- Client secrets kept server-side
- PIN-protected access
- Session tokens in httpOnly cookies

### General
- Config export excludes sensitive tokens and secrets
- Only necessary OAuth scopes requested
- No data sent to third parties (direct API calls only)

---

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

Requires: JavaScript ES6+, localStorage, Fetch API, CSS Flexbox

---

## License

MIT License - Feel free to modify and distribute.
