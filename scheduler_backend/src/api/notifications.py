"""
notifications.py

Handles outbound email notifications for event-related actions.

Supports:
- Sending event/invitation/reminder/update emails via SMTP
- Future extensibility (e.g., other notification channels)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from typing import List, Optional

# SMTP configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", 1025))  # Default: 1025 for local debug SMTP
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_SENDER = os.getenv("SMTP_SENDER", "no-reply@example.com")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() == "true"

class EmailNotificationType:
    INVITATION = "invitation"
    REMINDER = "reminder"
    UPDATE = "update"
    CANCELLATION = "cancellation"

# PUBLIC_INTERFACE
def send_email_notification(
    recipient: str,
    subject: str,
    body: str,
    subtype: str = "plain",
) -> bool:
    """
    Sends an email notification to a recipient.
    Returns True on success, False on failure (logs error).

    Args:
        recipient (str): recipient email address
        subject (str): subject
        body (str): plain text or HTML body
        subtype (str): "plain" or "html"
    """
    msg = MIMEMultipart()
    msg["From"] = SMTP_SENDER
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, _subtype=subtype))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_SENDER, recipient, msg.as_string())
        return True
    except Exception as ex:
        import logging
        logging.warning(f"Failed to send email to {recipient}: {ex}")
        return False

# PUBLIC_INTERFACE
def send_bulk_notifications(
    recipients: List[str],
    subject: str,
    body: str,
    subtype: str = "plain",
) -> int:
    """
    Sends notification emails to a list of recipients.
    Returns the count of successfully sent emails.
    """
    sent = 0
    for r in recipients:
        if send_email_notification(r, subject, body, subtype):
            sent += 1
    return sent

# PUBLIC_INTERFACE
def make_invitation_email(event_title: str, inviter: str, event_time: str, event_desc: Optional[str] = None) -> (str, str):
    """
    Returns a (subject, body) tuple for an event invitation email.
    """
    subject = f"You've been invited to '{event_title}'"
    body = f"""Hello,

You have been invited to the event "{event_title}" by {inviter}.

Event time: {event_time}
{f'Event description: {event_desc}' if event_desc else ''}

Please login to your account to view and respond to the invitation.

Best regards,
Collaborative Event Scheduler Team
"""
    return subject, body

# PUBLIC_INTERFACE
def make_event_reminder_email(event_title: str, event_time: str, event_desc: Optional[str] = None) -> (str, str):
    """Builds a reminder email for participants."""
    subject = f"Reminder: '{event_title}' is coming up"
    body = f"""Hello,

This is a reminder for the upcoming event: "{event_title}".

Scheduled for: {event_time}
{f'Event description: {event_desc}' if event_desc else ''}

Thank you,
Collaborative Event Scheduler Team
"""
    return subject, body

# PUBLIC_INTERFACE
def make_update_email(event_title: str, event_time: str, event_desc: Optional[str] = None) -> (str, str):
    """Builds an event update notification."""
    subject = f"Update: Event '{event_title}' has changed"
    body = f"""Hello,

There has been a change to the event: "{event_title}".

New time: {event_time}
{f'Description: {event_desc}' if event_desc else ''}

Please review the event in your account.

Best,
Collaborative Event Scheduler Team
"""
    return subject, body

# Additional templates (cancellation, etc.) can be added as needed.
