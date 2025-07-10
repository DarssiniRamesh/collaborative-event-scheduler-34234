"""
Event management (CRUD), participation, and invitation support for collaborative event scheduler.

- Includes Event and Participation models (with multi-user support)
- FastAPI endpoints for event creation, editing, deletion, and viewing
- SQLite persistence for events and participation
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, EmailStr
from .db import get_db_connection
from .auth import get_user_from_token, User

router = APIRouter(prefix="/events", tags=["events"])

# === Database Models ===

def create_event_and_participant_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    # Event table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )
        """
    )
    # Participation table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'invited',
            invited_by INTEGER,
            responded_at TEXT,
            UNIQUE(event_id, user_id, email),
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(invited_by) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()

# === Pydantic Models ===

class ParticipantInfo(BaseModel):
    id: int
    email: Optional[EmailStr]
    user_id: Optional[int]
    status: str
    invited_by: Optional[int]
    responded_at: Optional[str]

class EventBase(BaseModel):
    title: str = Field(..., description="Event title")
    description: Optional[str] = None
    start_time: datetime = Field(..., description="Event start time (ISO format)")
    end_time: datetime = Field(..., description="Event end time (ISO format)")
    location: Optional[str] = None

class EventCreate(EventBase):
    participants: Optional[List[EmailStr]] = Field(None, description="User emails to invite as participants")

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None

class EventResponse(EventBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    participants: List[ParticipantInfo]

# === Event CRUD Endpoints ===

# PUBLIC_INTERFACE
@router.post("/", status_code=201, response_model=EventResponse, summary="Create new event")
def create_event(
    event: EventCreate,
    user: User = Depends(get_user_from_token),
):
    """
    PUBLIC_INTERFACE
    Creates a new event owned by the authenticated user. Optionally invites participants by email.

    - participants: List of email addresses to invite/join
    """
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """INSERT INTO events
           (owner_id, title, description, start_time, end_time, location, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user.id,
            event.title,
            event.description,
            event.start_time.isoformat(),
            event.end_time.isoformat(),
            event.location,
            now,
            now,
        ),
    )
    eid = cur.lastrowid

    # Add participants
    participants_info = []
    participant_emails = event.participants or []
    for email in participant_emails:
        cur.execute(
            """INSERT OR IGNORE INTO event_participants
               (event_id, email, invited_by, status)
               VALUES (?, ?, ?, ?)""",
            (eid, email, user.id, "invited"),
        )
        participants_info.append(
            ParticipantInfo(
                id=cur.lastrowid,
                user_id=None,
                email=email,
                status="invited",
                invited_by=user.id,
                responded_at=None
            )
        )
    # Add owner as "accepted"
    cur.execute(
        """INSERT OR IGNORE INTO event_participants
           (event_id, user_id, email, invited_by, status, responded_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (eid, user.id, user.email, user.id, "accepted", now),
    )
    conn.commit()

    # Fetch and return the created event
    event_row = cur.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
    parts = cur.execute("SELECT * FROM event_participants WHERE event_id = ?", (eid,)).fetchall()
    participants = [
        ParticipantInfo(
            id=p[0],
            event_id=p[1] if len(p) > 1 else None,
            user_id=p[2],
            email=p[3],
            status=p[4],
            invited_by=p[5],
            responded_at=p[6],
        ) for p in parts
    ]
    conn.close()
    return EventResponse(
        id=event_row[0],
        owner_id=event_row[1],
        title=event_row[2],
        description=event_row[3],
        start_time=event_row[4],
        end_time=event_row[5],
        location=event_row[6],
        created_at=event_row[7],
        updated_at=event_row[8],
        participants=participants,
    )

# PUBLIC_INTERFACE
@router.get("/", response_model=List[EventResponse], summary="List events for user (owned or invited)")
def list_events(
    user: User = Depends(get_user_from_token),
    q: Optional[str] = Query(None, description="Full text search title/desc/location"),
):
    """
    PUBLIC_INTERFACE
    Returns all events where user is the owner or a participant,
    optionally filtered by search query text.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    base_query = """
        SELECT DISTINCT e.* FROM events e
        JOIN event_participants p ON p.event_id = e.id
        WHERE (p.user_id = ? OR p.email = ?)
    """
    params = (user.id, user.email)
    if q:
        base_query += " AND (e.title LIKE ? OR e.description LIKE ? OR e.location LIKE ?)"
        like = f"%{q}%"
        params += (like, like, like)
    cur.execute(base_query, params)
    rows = cur.fetchall()
    # For each event, get participants
    events = []
    for row in rows:
        parts = cur.execute(
            "SELECT * FROM event_participants WHERE event_id=?", (row[0],)
        ).fetchall()
        participants = [
            ParticipantInfo(
                id=p[0],
                event_id=p[1] if len(p) > 1 else None,
                user_id=p[2],
                email=p[3],
                status=p[4],
                invited_by=p[5],
                responded_at=p[6],
            ) for p in parts
        ]
        events.append(
            EventResponse(
                id=row[0],
                owner_id=row[1],
                title=row[2],
                description=row[3],
                start_time=row[4],
                end_time=row[5],
                location=row[6],
                created_at=row[7],
                updated_at=row[8],
                participants=participants,
            )
        )
    conn.close()
    return events

# PUBLIC_INTERFACE
@router.get("/{event_id}", response_model=EventResponse, summary="Get event details")
def get_event(
    event_id: int, user: User = Depends(get_user_from_token)
):
    """
    PUBLIC_INTERFACE
    Returns event details for a given event if the user is an owner or participant.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    event = cur.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found")
    # Check user access
    access = cur.execute(
        "SELECT 1 FROM event_participants WHERE event_id=? AND (user_id=? OR email=?)",
        (event_id, user.id, user.email),
    ).fetchone()
    if not access:
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")
    parts = cur.execute(
        "SELECT * FROM event_participants WHERE event_id=?", (event_id,)
    ).fetchall()
    participants = [
        ParticipantInfo(
            id=p[0],
            event_id=p[1] if len(p) > 1 else None,
            user_id=p[2],
            email=p[3],
            status=p[4],
            invited_by=p[5],
            responded_at=p[6],
        ) for p in parts
    ]
    conn.close()
    return EventResponse(
        id=event[0],
        owner_id=event[1],
        title=event[2],
        description=event[3],
        start_time=event[4],
        end_time=event[5],
        location=event[6],
        created_at=event[7],
        updated_at=event[8],
        participants=participants,
    )

# PUBLIC_INTERFACE
@router.put("/{event_id}", response_model=EventResponse, summary="Update existing event")
def update_event(
    event_id: int,
    update: EventUpdate,
    user: User = Depends(get_user_from_token),
):
    """
    PUBLIC_INTERFACE
    Update title, description, time, location (owner only).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Ensure only owner can update
    row = cur.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found")
    if row[1] != user.id:
        conn.close()
        raise HTTPException(status_code=403, detail="Only event owner can update")
    # Generate patch
    fields, values = [], []
    for fld in ["title", "description", "start_time", "end_time", "location"]:
        val = getattr(update, fld)
        if val is not None:
            fields.append(f"{fld}=?")
            values.append(val.isoformat() if "time" in fld else val)
    if fields:
        fields.append("updated_at=?")
        values.append(datetime.utcnow().isoformat())
        values.append(event_id)
        cur.execute(f"UPDATE events SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()
    # Return event
    row = cur.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    parts = cur.execute(
        "SELECT * FROM event_participants WHERE event_id=?", (event_id,)
    ).fetchall()
    participants = [
        ParticipantInfo(
            id=p[0],
            event_id=p[1] if len(p) > 1 else None,
            user_id=p[2],
            email=p[3],
            status=p[4],
            invited_by=p[5],
            responded_at=p[6],
        ) for p in parts
    ]
    conn.close()
    return EventResponse(
        id=row[0],
        owner_id=row[1],
        title=row[2],
        description=row[3],
        start_time=row[4],
        end_time=row[5],
        location=row[6],
        created_at=row[7],
        updated_at=row[8],
        participants=participants,
    )

# PUBLIC_INTERFACE
@router.delete("/{event_id}", status_code=204, summary="Delete event")
def delete_event(
    event_id: int, user: User = Depends(get_user_from_token)
):
    """
    PUBLIC_INTERFACE
    Deletes an event. Only the owner can delete.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found")
    if row[1] != user.id:
        conn.close()
        raise HTTPException(status_code=403, detail="Only event owner can delete the event")
    # Delete event (cascade will delete participants)
    cur.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    return

# PUBLIC_INTERFACE
@router.post("/{event_id}/respond", summary="Respond to event invitation (accept/decline)")
def respond_to_invitation(
    event_id: int,
    response_status: str = Query(..., description="Response status: accepted/declined"),
    user: User = Depends(get_user_from_token),
):
    """
    PUBLIC_INTERFACE
    User responds to event invitation (accept/decline).
    """
    if response_status not in ("accepted", "declined"):
        raise HTTPException(status_code=400, detail="Status must be accepted or declined")
    conn = get_db_connection()
    cur = conn.cursor()
    p = cur.execute(
        "SELECT * FROM event_participants WHERE event_id=? AND (user_id=? OR email=?)",
        (event_id, user.id, user.email),
    ).fetchone()
    if not p:
        conn.close()
        raise HTTPException(status_code=404, detail="Invitation not found")
    cur.execute(
        "UPDATE event_participants SET status=?, responded_at=? WHERE id=?",
        (response_status, datetime.utcnow().isoformat(), p[0]),
    )
    conn.commit()
    conn.close()
    return {"success": True}


# Run on import (after app start: ensure tables exist)
create_event_and_participant_tables()
