# Email Kanban Backend

FastAPI backend with SQLite for secure hosting of the Email Kanban app.

## Features

- **Secure OAuth proxy** - Client secrets never exposed to frontend
- **Token encryption** - Refresh tokens stored encrypted in SQLite
- **Caching** - Emails/tasks cached for 5 minutes to reduce API calls
- **PIN authentication** - Simple PIN-based access control
- **Docker ready** - Easy deployment with docker-compose

## Quick Start (Development)

1. **Setup environment:**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

3. **Run the server:**
   ```bash
   uvicorn main:app --reload --port 8001
   ```

4. **Serve the frontend:**
   ```bash
   # In another terminal, from the parent directory
   python -m http.server 8000
   ```

5. **Open** http://localhost:8000/index-backend.html

## Docker Deployment

1. **Setup environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Run with docker-compose:**
   ```bash
   docker-compose up -d
   ```

3. **Open** http://localhost:8000

## OAuth Setup

### Microsoft (Office 365)

1. Go to [Azure Portal](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Create new app registration
3. Add redirect URI: `http://localhost:8001/auth/callback/office365`
4. Create client secret
5. Add to `.env`:
   ```
   MICROSOFT_CLIENT_ID=your-client-id
   MICROSOFT_CLIENT_SECRET=your-client-secret
   ```

### Google (Gmail)

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 Client ID
3. Add redirect URI: `http://localhost:8001/auth/callback/gmail`
4. Add to `.env`:
   ```
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```

### TickTick

1. Go to [TickTick Developer](https://developer.ticktick.com/manage)
2. Create new app
3. Add redirect URI: `http://localhost:8001/auth/callback/ticktick`
4. Add to `.env`:
   ```
   TICKTICK_CLIENT_ID=your-client-id
   TICKTICK_CLIENT_SECRET=your-client-secret
   ```

## Production Deployment

For production, update these settings:

1. **Generate secure secret key:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Update `.env`:**
   ```
   APP_SECRET_KEY=your-generated-key
   APP_PIN=your-secure-pin
   BASE_URL=https://your-domain.com/api
   FRONTEND_URL=https://your-domain.com
   ```

3. **Update OAuth redirect URIs** in all provider dashboards to use your production domain

4. **Deploy with HTTPS** - Use a reverse proxy like nginx or Caddy

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/login | Login with PIN |
| POST | /auth/logout | Logout |
| GET | /auth/check | Check authentication |
| GET | /auth/authorize/{provider} | Start OAuth flow |
| GET | /auth/callback/{provider} | OAuth callback |
| GET | /accounts | List accounts |
| POST | /accounts | Create account |
| GET | /accounts/{id} | Get account details |
| PATCH | /accounts/{id} | Update account |
| DELETE | /accounts/{id} | Delete account |
| GET | /accounts/{id}/items | Get emails/tasks |
| POST | /accounts/{id}/sync | Force refresh |
| POST | /accounts/{id}/emails/{id}/archive | Archive email |
| POST | /accounts/{id}/emails/{id}/star | Toggle star |
| POST | /accounts/{id}/tasks/{id}/complete | Toggle task completion |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend                           │
│                  (index-backend.html)                   │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP/HTTPS
┌─────────────────────────▼───────────────────────────────┐
│                   FastAPI Backend                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   OAuth     │  │   Cache     │  │   Token         │ │
│  │   Proxy     │  │   Layer     │  │   Encryption    │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                     SQLite DB                           │
│  ┌─────────────┐  ┌─────────────────────────────────┐  │
│  │  Accounts   │  │  Cached Items (emails/tasks)    │  │
│  │  (tokens)   │  │                                 │  │
│  └─────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```
