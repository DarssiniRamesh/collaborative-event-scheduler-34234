# E2E Integration Test Plan: Collaborative Scheduler

Covers: FastAPI backend and React frontend e2e integration (ports 3001 and 4000).  
Scope: Auth (Google/SSO), CORS, event CRUD, real-time WebSocket updates, multi-user participant management, notifications, API robustness and error handling.  
Tools: 
- Manual browser testing (for SSO, email, and UI flows)
- Automated scripts (e.g., using `pytest`, Selenium, Playwright, or test React app with live backend)

---

## I. Auth & Token Issue (Google/Generic SSO)
1. Open React frontend (`http://localhost:4000`).
2. Click "Sign in with Google"/"SSO Sign In":
   - Should redirect to `/auth/google/login` or `/auth/oauth2/login`.
   - On success, redirected to `/auth/login-success?token=...`.  
   - Frontend stores access token and uses as Bearer for all API calls.
   - JWT issued by backend is valid (verify payload, expiration, etc).
3. Open `/auth/me` with Bearer token:
   - Returns user profile info (id, email, name, picture, provider).
   - Auth errors (expired or missing JWT) get clean `401` error JSON, with no CORS block.
4. Log out, confirm protected endpoints now 401.

## II. CORS Compliance: REST and WebSocket
1. With the frontend running on port 4000 and backend on 3001:
   - REST fetches to `/events`, `/auth/me`, `/db-health` succeed.
   - All HTTP methods (GET, POST, PUT, DELETE) allowed.
   - Preflight OPTIONS requests succeed (manual: Chrome DevTools > Network).
   - No `CORS`/browser errors present in console for any REST calls.
2. WebSocket: Open `ws://localhost:3001/ws/events?token=JWT_TOKEN` from frontend.
   - Connection succeeds.
   - Messages are received upon event changes.
   - No browser/network policy errors.

## III. Event CRUD + Multi-Participant Management
1. Create new event:
   - POST `/events` with title, time, and multiple participant emails.
   - Response contains event with participants array.
   - Backend sends invitation emails to those addresses.
   - Email inbox of invited user receives invitation.
2. Edit event:
   - PUT `/events/:id` as owner; update title, time, participants.
   - Notification banners or toasts appear for updated events in all open frontends (real-time).
   - Invited users receive update emails.
   - Non-owners cannot update (should get 403).
3. Delete event:
   - DELETE `/events/:id` as owner. All participants see deletion banner/notification.
   - Ensure only owner can delete (403 for non-owner).
4. List/Query events:
   - GET `/events` returns all events user is owner, invited, or participant.
   - Can query by search string.

## IV. Real-Time WebSocket Sync
1. Connect two users, both logged in with their tokens (different browser windows).
2. User A creates/edits/deletes event. User B's window receives real-time notification via WebSocket—UI updates without manual refresh.
3. Participant accepts/declines invite. All windows see status change in real time.

## V. Email Notification Triggers
1. Event creation (with invites): All invitees receive email.
2. Event update: All participants (except updater) receive update email.
3. Ensure banners/UI indicators are shown to users for new invites, updates, and deletions.
4. Backend logs show success or error for each email sent.

## VI. API Robustness & Error Handling
1. Expired or invalid token:
   - API returns HTTP 401 with error JSON, not HTML or generic error.
   - WebSocket closes with policy violation code if token invalid.
2. Event CRUD with missing fields: API returns 400 with JSON detail.
3. Forbidden actions (e.g., user tries to edit/delete event not owned): Returns 403.
4. Database outage (simulate by renaming DB file): `/db-health` returns 503, error banner in frontend.
5. Confirm *no* 4xx/5xx browser console errors that are caused by CORS or network policy.

## VII. OpenAPI/Swagger Docs
1. `/interfaces/openapi.json` is up to date and matches live API structure.
2. Can import OpenAPI to Swagger UI or Postman for manual API trials.

---

## Manual Checklist

- [ ] SSO login works and token is issued/captured by frontend.
- [ ] All REST endpoints reachable from frontend with Bearer token.
- [ ] All CORS headers present and allowed. No browser CORS errors.
- [ ] WebSocket connections work from React and receive real-time updates.
- [ ] Event CRUD functions end-to-end (owner and invited users, multi-user scenarios).
- [ ] Email notifications are sent for invitations/updates.
- [ ] Error responses are consistent, JSON-formatted, and robust.
- [ ] UI shows banners for notifications/errors.
- [ ] APIs and sockets clearly reject expired/invalid tokens (no CORS/network errors).
- [ ] Database health API and UI indicator work properly.

---

## Automated Test Suggestions

- Use Playwright, Selenium, or Cypress for UI+socket E2E tests (simulate login, event CRUD, real-time).
- Use pytest + httpx for token/REST static tests (API contract, error conditions, CORS preflight).
- Use Python/JS WebSocket client scripts to verify socket connection, auth, and event push flows.
- Use a mock SMTP server (such as `mailhog` or `smtp4dev`) to capture and verify outgoing emails.

---

## Known Edge Cases to Test

- User invites self as participant (should behave gracefully).
- Same user receives multiple invitations (handle cleanly).
- Event deleted while user opening event details (UI updates properly).
- Token expires mid-session; user is forced to re-login smoothly (UI fallback tested).
- CORS policy tightened to allow only `http://localhost:4000`; confirm forbidden origins correctly blocked, allowed origin works.

---

## References

- See project README for integration endpoints and OAuth details.
- API schema: `collaborative-event-scheduler-34234/scheduler_backend/interfaces/openapi.json`
- For any changes, regenerate the OpenAPI via `generate_openapi.py` (if endpoints were updated).

---
