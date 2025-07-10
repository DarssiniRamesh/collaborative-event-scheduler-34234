# Project Repository

This is the initial README file for the project.

---

## Integration Guide: Connecting React (Port 4000) to FastAPI Backend (Port 3001)

### 1. CORS & API Access

The backend (`/scheduler_backend/src/api/main.py`) uses permissive CORS. By default, any origin is allowed. If you wish to restrict CORS to the React dev server, set:

```env
CORS_ALLOW_ORIGINS=http://localhost:4000,http://127.0.0.1:4000
```

in your `.env` file for the backend.

**Test CORS**: A React app (or any JS frontend) can access all REST and WebSocket endpoints at `http://localhost:3001`.

### 2. SSO Login (Google/Generic OAuth2)

#### How login works

- User clicks "Sign in with Google" or "SSO Sign In" in React UI.
- Frontend opens `GET /auth/google/login` (or `/auth/oauth2/login`) **in a new window/tab**.
- On success, backend redirects to `/auth/login-success?token=...` and sets cookie.
- **Your SPA must capture the JWT token** (see below).

**React Code Example:**
```js
// SSO Login Button
window.open('http://localhost:3001/auth/google/login', '_self');

// Handle callback
// In your SPA, route '/auth/login-success?token=...' should:
// 1. grab the token from the query string
// 2. store token in memory/storage (localStorage/sessionStorage/cookie)
// 3. use token as Bearer for further API calls
```

### 3. REST API Usage

**Base URL:** `http://localhost:3001`

- All event and user endpoints require the JWT access token (as Bearer header).
- Sample REST request (with fetch):

```js
const token = localStorage.getItem('access_token');
fetch('http://localhost:3001/events', {
  headers: { 'Authorization': 'Bearer ' + token }
});
```

**Available endpoints:** (see `/interfaces/openapi.json` for details)

- `/events/` (CRUD)
- `/auth/*` (SSO, user info, logout)
- `/db-health` (DB status)
- `/` (service health)

### 4. WebSocket Real-Time Updates

**Endpoint:** `ws://localhost:3001/ws/events?token=JWT_TOKEN`

**React sample:**
```js
const ws = new WebSocket("ws://localhost:3001/ws/events?token=" + token);
ws.onmessage = event => {
  const { type, payload } = JSON.parse(event.data);
  // handle event, e.g. show toast/refresh UI
};
```
- All event changes (created/updated/deleted/invited/participation) are broadcasted.
- Keep connection open to get live updates!

### 5. Email Notification Flow

- When inviting users to events, the backend sends email invitations using SMTP settings in `.env`.
- No frontend action is required for emailing; a participant will receive an email if registered.

### 6. Health Check

- REST: `GET /` returns {"message": "Healthy"}
- DB:   `GET /db-health` returns `{"db_status": "ok"}` or `{"db_status": "error"}`

---

### 7. Error Handling

- All endpoints use FastAPI error responses (e.g. 401 for auth failures).
- JWT expiry, auth errors, or permission errors return JSON error responses suitable for frontend handling.

---

### 8. OpenAPI/Swagger

- The full API schema is available at [`/interfaces/openapi.json`](./scheduler_backend/interfaces/openapi.json).
- For rapid React prototyping and testing, use the schema with tools like Swagger UI or Postman.

---

#### For further integration help, contact the backend maintainer.