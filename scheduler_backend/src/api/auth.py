"""
OAuth2 SSO, user management, and authentication logic for the collaborative event scheduler.

This module includes:
- User model and persistence with SQLite
- FastAPI endpoints for OAuth2 login (Google/generic)
- Token generation and session management
- Decorators and helpers for authenticated endpoints
"""

import os
import httpx
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from jose import jwt, JWTError

from .db import get_db_connection

# === CONFIGURATION ===
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3001/auth/google/callback")
SECRET_KEY = os.getenv("JWT_SECRET", "dev_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 8  # 8 hours

# For generic OAuth2
OAUTH2_CLIENT_ID = os.getenv("OAUTH2_CLIENT_ID")
OAUTH2_CLIENT_SECRET = os.getenv("OAUTH2_CLIENT_SECRET")
OAUTH2_AUTH_URL = os.getenv("OAUTH2_AUTH_URL")  # e.g., https://provider.com/oauth2/authorize
OAUTH2_TOKEN_URL = os.getenv("OAUTH2_TOKEN_URL")
OAUTH2_USERINFO_URL = os.getenv("OAUTH2_USERINFO_URL")
OAUTH2_REDIRECT_URI = os.getenv("OAUTH2_REDIRECT_URI", "http://localhost:3001/auth/oauth2/callback")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")  # used for DRF token injection (not for browser SSO)

router = APIRouter(prefix="/auth", tags=["auth"])

# === SQLite User Model and Management ===

class User(BaseModel):
    """User model for the scheduler app."""
    id: int
    email: EmailStr
    name: str
    picture: Optional[str]
    provider: str = Field(..., description="OAuth provider, e.g. 'google' or generic id")
    provider_id: str = Field(..., description="Subject/user id from provider")

def create_user_table():
    """Create the users table in SQLite, if not exists."""
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            picture TEXT,
            provider TEXT NOT NULL,
            provider_id TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def get_user_by_email(email: str) -> Optional[User]:
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(id=row[0], email=row[1], name=row[2], picture=row[3], provider=row[4], provider_id=row[5])
    return None

def get_user_by_provider_id(provider: str, provider_id: str) -> Optional[User]:
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT * FROM users WHERE provider = ? AND provider_id = ?",
        (provider, provider_id),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(id=row[0], email=row[1], name=row[2], picture=row[3], provider=row[4], provider_id=row[5])
    return None

def create_user(email: str, name: str, picture: str, provider: str, provider_id: str) -> User:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, name, picture, provider, provider_id) VALUES (?, ?, ?, ?, ?)",
        (email, name, picture, provider, provider_id),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return User(id=uid, email=email, name=name, picture=picture, provider=provider, provider_id=provider_id)

def get_or_create_user(email: str, name: str, picture: str, provider: str, provider_id: str) -> User:
    u = get_user_by_email(email)
    if u:
        return u
    return create_user(email, name, picture, provider, provider_id)

# === JWTs AND TOKENS ===

class Token(BaseModel):
    """PUBLIC_INTERFACE
    OAuth2 access token for authenticated session.
    """
    access_token: str
    token_type: str = "bearer"

def create_access_token(*, data: dict, expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": int(__import__("time").time()) + expires_in})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user_from_token(token: str = Depends(oauth2_scheme)) -> User:
    """PUBLIC_INTERFACE
    Dependency for routes. Gets user from JWT or raises 401.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        email = payload.get("email")
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="Token payload invalid.")
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found.")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# === GOOGLE OAUTH2 FLOW ===

@router.get("/google/login", summary="Initiate Google OAuth2 Login")
def google_login():
    """PUBLIC_INTERFACE
    Redirects to Google's OAuth2 authorization URL for sign-in.
    """
    google_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        "?response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=select_account"
    )
    return RedirectResponse(google_url)

@router.get("/google/callback", summary="Google OAuth2 Callback")
async def google_callback(request: Request, code: str):
    """PUBLIC_INTERFACE
    Handles callback from Google. Exchanges code for token, fetches user profile, issues JWT.
    """
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        token_resp = await client.post("https://oauth2.googleapis.com/token", data=token_data)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Google token request failed"
            )
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        # Use access_token to fetch user info from Google
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch userinfo from Google")
        userinfo = userinfo_resp.json()
    # Create/fetch user in DB
    user = get_or_create_user(
        email=userinfo["email"],
        name=userinfo.get("name", userinfo["email"]),
        picture=userinfo.get("picture"),
        provider="google",
        provider_id=userinfo["id"],
    )
    # Issue our access token
    token = create_access_token(data={"user_id": user.id, "email": user.email, "provider": user.provider})
    # For browser use (SPA), return token in response as JSON
    response = RedirectResponse(url=f"/auth/login-success?token={token}")
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response

# === GENERIC OAUTH2 FLOW ===

@router.get("/oauth2/login", summary="Initiate generic OAuth2 login")
def generic_oauth2_login():
    """PUBLIC_INTERFACE
    Redirects to configured OAuth2 provider's authorization endpoint.
    """
    auth_url = (
        f"{OAUTH2_AUTH_URL}"
        "?response_type=code"
        f"&client_id={OAUTH2_CLIENT_ID}"
        f"&redirect_uri={OAUTH2_REDIRECT_URI}"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=select_account"
    )
    return RedirectResponse(auth_url)

@router.get("/oauth2/callback", summary="Generic OAuth2 Callback")
async def generic_oauth2_callback(request: Request, code: str):
    """PUBLIC_INTERFACE
    Handles OAuth2 callback for a generic provider.
    """
    async with httpx.AsyncClient() as client:
        token_data = {
            "code": code,
            "client_id": OAUTH2_CLIENT_ID,
            "client_secret": OAUTH2_CLIENT_SECRET,
            "redirect_uri": OAUTH2_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        token_resp = await client.post(OAUTH2_TOKEN_URL, data=token_data)
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="OAuth2 token request failed")
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        # Optionally id_token, depends on provider
        userinfo_resp = await client.get(
            OAUTH2_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="OAuth2 userinfo failed")
        userinfo = userinfo_resp.json()
    # Map userinfo to our fields (may require mapping depending on provider response)
    user = get_or_create_user(
        email=userinfo["email"],
        name=userinfo.get("name", userinfo["email"]),
        picture=userinfo.get("picture"),
        provider="oauth2",
        provider_id=str(userinfo["sub"] if "sub" in userinfo else userinfo["id"]),
    )
    token = create_access_token(data={"user_id": user.id, "email": user.email, "provider": user.provider})
    response = RedirectResponse(url=f"/auth/login-success?token={token}")
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response

# === SESSION INFO, LOGOUT, AND MISC ===

class UserResponse(BaseModel):
    """PUBLIC_INTERFACE
    User info returned after authentication.
    """
    id: int
    email: EmailStr
    name: str
    picture: Optional[str]
    provider: str

@router.get("/me", summary="Get current user", response_model=UserResponse)
def get_me(user: User = Depends(get_user_from_token)):
    """PUBLIC_INTERFACE
    Returns info for the current authenticated user.
    """
    return UserResponse(**user.model_dump())

@router.get("/login-success", summary="Frontend auth handler/landing")
def login_success(token: str):
    """PUBLIC_INTERFACE
    For SPA callback handling. Just returns a success message and access token.
    """
    return JSONResponse({"success": True, "access_token": token})

@router.post("/logout", summary="Logs out by clearing browser token cookie")
def logout():
    """PUBLIC_INTERFACE
    Logs the user out by deleting access_token cookie.
    """
    resp = JSONResponse({"success": True})
    resp.delete_cookie("access_token")
    return resp

# Ensure creation of user table after app start
create_user_table()
