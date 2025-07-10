import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .db import check_db_connection

# Import authentication routes
from .auth import router as auth_router
from .event import router as event_router
from .ws import router as ws_router

# Load env variables from .env file if present
load_dotenv()

PORT = int(os.getenv("PORT", "3001"))
# Remove unused OAUTH_CLIENT_ID/SECRET to avoid confusion—they are not used here
# OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
# OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# CORS
CORS_ALLOW_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")]

app = FastAPI(
    title="Collaborative Scheduler Backend",
    description="Backend for Collaborative Event Scheduler with OAuth and SQLite DB",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Service health and diagnostics"},
        {"name": "database", "description": "Database connectivity and diagnostics"},
        {"name": "auth", "description": "User authentication and SSO endpoints"},
    ]
)

# Mount authentication endpoints
app.include_router(auth_router)
app.include_router(event_router)
app.include_router(ws_router)

# Apply open CORS policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS if CORS_ALLOW_ORIGINS != [""] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PUBLIC_INTERFACE
@app.get("/", tags=["health"], summary="Health Check", description="Simple service health check endpoint")
def health_check():
    """
    Returns a general health status for the service.
    """
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.get("/db-health", tags=["database"], summary="Database Health Check", description="Check SQLite DB connectivity")
def db_health_check():
    """
    Returns DB health status: verifies if the backend is able to connect to the configured SQLite database.
    Returns:
        200 OK + {"db_status": "ok"} if DB connection was successful.
        503 Service Unavailable + {"db_status": "error"} if DB could not be reached.
    """
    if check_db_connection():
        return {"db_status": "ok"}
    return JSONResponse(content={"db_status": "error"}, status_code=503)

# PUBLIC_INTERFACE
@app.get("/ws-docs", tags=["websockets"], summary="WebSocket usage", description="Get info about real-time WebSocket API and how to connect")
def websocket_docs():
    """
    Returns WebSocket usage notes for frontend developers and API consumers.

    - Connect to ws://<host>:<port>/ws/events?token=JWT_TOKEN
    - JWT token is required (same as REST API bearer).
    - Notifications are sent when events are created, updated, deleted, or invites/participations change.
    - Message format:
        {
            "type": "created|updated|deleted|invited|participation",
            "payload": {...}  # event data or minimal info
        }
    """
    return {
        "websocket_url": "/ws/events?token=YOUR_JWT_TOKEN",
        "connection_note": "Use a valid bearer JWT (same as REST API).",
        "message_types": [
            "created", "updated", "deleted", "invited", "participation"
        ],
        "description": "The backend broadcasts real-time event changes to all connected clients via the WebSocket channel.",
        "example": {
            "type": "updated",
            "payload": {
                "id": 12,
                "title": "Board Meeting",
                # ...
            }
        },
    }
