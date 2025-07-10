# Collaborative Event Scheduler – End-to-End Developer & Environment Guide

This document covers how to configure, run, and integrate the real-time event scheduler, including both the FastAPI backend (`scheduler_backend`) and the React frontend (`scheduler_frontend`). It also details all environment variables (OAuth, SMTP, CORS, ports), integration workflow, and common troubleshooting advice.

---

## 1. Environment Variables and Example Files

### Backend (`scheduler_backend/.env.example`)

Below are all environment variables used by the backend. Copy and rename this template to `.env` in your backend directory and fill in the values.

```env
# === Server ===
PORT=3001

# === Database ===
DB_PATH=app.db  # Default: [repo_root]/scheduler_backend/app.db

# === CORS ===
CORS_ALLOW_ORIGINS=http://localhost:4000,http://127.0.0.1:4000
# (Comma-separated frontend URLs allowed; or * for permissive in dev.)

# === JWT / Auth ===
JWT_SECRET=dev_secret_key  # Use a strong secret in production!

# === Google OAuth2 ===
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:3001/auth/google/callback

# === Generic OAuth2 Provider (optional alternative SSO) ===
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_AUTH_URL=https://provider.com/oauth2/authorize
OAUTH2_TOKEN_URL=https://provider.com/oauth2/token
OAUTH2_USERINFO_URL=https://provider.com/oauth2/userinfo
OAUTH2_REDIRECT_URI=http://localhost:3001/auth/oauth2/callback

# === SMTP/Email notifications ===
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_SENDER=no-reply@example.com
SMTP_USE_TLS=false  # set to 'true' if using TLS
```

### Frontend (`scheduler_frontend/.env.example`)

In the frontend, you'll typically need to expose the API and WebSocket endpoints, and provide the Google OAuth client ID. Copy this to `.env` in your frontend directory:

```env
# === Backend API base URL ===
REACT_APP_API_BASE_URL=http://localhost:3001

# === WebSocket endpoint for real-time updates ===
REACT_APP_WS_URL=ws://localhost:3001/ws/events

# === Google OAuth Client ID (same as backend one) ===
REACT_APP_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

**Note:** If the frontend needs to configure any API URLs or OAuth IDs, it should reference variables as above (REACT_APP_*) for Create React App or similar build systems.

---

## 2. OAuth SSO & SMTP Configuration – Backend

- **Google SSO:** The backend requires a Google OAuth Client ID/Secret.
  - Set up credentials at Google Developer Console.
  - Make sure your project's **Authorized redirect URI** matches `GOOGLE_REDIRECT_URI`.
- **Generic OAuth2:** Fill in the OAUTH2 fields for a custom SSO provider (leave blank if unused).
- **SMTP:** By default, the backend sends mail via SMTP for event invitations/updates. For local development, use a tool like [MailHog](https://github.com/mailhog/MailHog) or [smtp4dev](https://github.com/rnwood/smtp4dev); set SMTP_HOST/PORT to point to it. For production, supply real SMTP credentials.

---

## 3. Developer Run Instructions

### Backend

1. **Install Dependencies:**
   ```bash
   cd scheduler_backend
   pip install -r requirements.txt
   ```
2. **Prepare your `.env` file:**  
   Copy `.env.example` to `.env` and fill in credentials.
3. **Run the backend server:**
   ```bash
   uvicorn src.api.main:app --reload --port 3001
   ```
   If port is in use, adjust `PORT` in your `.env` and/or the above command.

4. **Regenerate OpenAPI docs (if endpoints are updated):**
   ```bash
   python src/api/generate_openapi.py
   ```

### Frontend

1. **Install Dependencies:**  
   ```bash
   cd scheduler_frontend
   npm install
   ```
2. **Prepare your `.env` file:**  
   Copy `.env.example` to `.env` and set values.
3. **Run the development server:**
   ```bash
   npm start
   ```
   By default, runs on port **4000**.

---

## 4. Integration Workflow

- **Frontend login initiates SSO:** User clicks "Sign in with Google" or "SSO". This triggers the backend's `/auth/google/login`, which redirects for OAuth. Successful login issues JWT token (provided to frontend as query param).
- **Frontend stores JWT:** React captures the token in `/auth/login-success?token=...`, saves it (cookies/localStorage), and passes it as Bearer to all further backend API calls.
- **All protected REST API requests use Bearer JWT:** See the [README.md](../README.md) for fetch examples.
- **Real-time updates:** The frontend opens a WebSocket to `ws://localhost:3001/ws/events?token=...` using the same JWT. Backend pushes notifications for event changes.
- **Email notifications:** When users are invited/updated in an event, the backend emails participants automatically via SMTP – no separate frontend action required.
- **CORS:** Ensure the backend’s `CORS_ALLOW_ORIGINS` matches your frontend dev base URL(s) exactly.

---

## 5. Troubleshooting & Common Issues

- **SSO Login fails / JWT not returned:** Ensure Google OAuth credentials are correct and `GOOGLE_REDIRECT_URI` matches the URI configured in Google Developers Console.
- **Invalid token / 401 errors:** Tokens may expire (8h by default). User must re-login. Check browser storage and backend logs for clues.
- **CORS errors in browser:**  
  - Confirm backend and frontend domains/ports in `CORS_ALLOW_ORIGINS`.
  - For dev, set to `*` or the full frontend origin.
  - Preflight (OPTIONS) errors often mean missing headers or misconfiguration.
- **WebSocket fails to connect:**  
  - Ensure backend is running and accessible on the specified port.
  - JWT token must be valid and present in connection query.
- **No emails received:**  
  - For development, check your SMTP dev server/mailhog inbox.
  - For production, verify SMTP details and backend logs for send errors.
- **Database connection errors:**  
  - Ensure `DB_PATH` is writable and the path exists.
  - Use `/db-health` endpoint to check health.

---

## 6. References

- **API OpenAPI/Swagger spec:** [`/interfaces/openapi.json`](../scheduler_backend/interfaces/openapi.json)
- **README:** See [../README.md](../README.md) for quick integration walkthrough and code examples.
- **Sample E2E test plan:** See [`../scheduler_backend/tests/e2e_integration_test_plan.md`](../scheduler_backend/tests/e2e_integration_test_plan.md) for manual and suggested automated test checklist.

---

## 7. Contact

For further help, reach out to the backend maintainer or consult the project issue tracker.
