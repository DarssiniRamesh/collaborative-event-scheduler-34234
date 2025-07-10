import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .db import check_db_connection

# Load env variables from .env file if present
load_dotenv()

PORT = int(os.getenv("PORT", "3001"))
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# CORS
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")

app = FastAPI(
    title="Collaborative Scheduler Backend",
    description="Backend for Collaborative Event Scheduler with OAuth and SQLite DB",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Service health and diagnostics"},
        {"name": "database", "description": "Database connectivity and diagnostics"},
    ]
)

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
