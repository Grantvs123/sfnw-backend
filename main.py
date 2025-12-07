import os
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --------------------------------------------------------------------
# FASTAPI APP
# --------------------------------------------------------------------
app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("maxi-backend")

# --------------------------------------------------------------------
# ENV + GOOGLE CALENDAR SETUP
# --------------------------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

missing = []
if not TWILIO_ACCOUNT_SID:
    missing.append("TWILIO_ACCOUNT_SID")
if not TWILIO_AUTH_TOKEN:
    missing.append("TWILIO_AUTH_TOKEN")
if not TWILIO_FROM_NUMBER:
    missing.append("TWILIO_FROM_NUMBER")
if not GOOGLE_CALENDAR_ID:
    missing.append("GOOGLE_CALENDAR_ID")
if not GOOGLE_SERVICE_ACCOUNT_JSON:
    missing.append("GOOGLE_SERVICE_ACCOUNT_JSON")

if missing:
    logger.warning("Missing environment variables: %s", missing)
else:
    logger.info("All expected environment variables are present.")


def twiml(xml: str) -> PlainTextResponse:
    """Return TwiML with correct content-type."""
    return PlainTextResponse(xml, media_type="application/xml")


def get_calendar_service():
    """
    Build a Google Calendar service from the JSON stored in
    GOOGLE_SERVICE_ACCOUNT_JSON. Returns None if misconfigured.
    """
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_CALENDAR_ID:
        logger.warning("Google Calendar env vars not fully configured; skipping Calendar integration.")
        return None

    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        logger.error("Failed to build Google Calendar service: %s", e)
        return None


def create_calendar_event(summary: str, description: str) -> None:
    """
    Create a simple 30-minute event starting 'now' on the configured calendar.
    If Calendar is not configured or fails, we just log and continue.
    """
    service = get_calendar_service()
    if service is None:
        return

    now = datetime.now(timezone.utc)
    end = now + timedelta(minutes=30)

    event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": now.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    try:
        service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        logger.info("Created Google Calendar event: %s", summary)
    except HttpError as e:
        logger.error("Google Calendar API error: %s", e)
    except Exception as e:
        logger.error("Unexpected error creating Calendar event: %s", e)


# --------------------------------------------------------------------
# HEALTH & VERSION
# --------------------------------------------------------------------
@app.get("/status")
def status():
    return {"status": "running", "message": "Maxi backend is online."}


@app.get("/version")
def version():
    return {"version": "1.0.0"}


# --------------------------------------------------------------------
# VOICE: INBOUND CALL
# Twilio: “A call comes in”  ->  POST https://sfnw-backend-production.up.railway.app/voice/inbound
# --------------------------------------------------------------------
@app.post("/voice/inbound")
async def voice_inbound(request: Request):
    form = await request.form()
    from_number = form.get("From", "Unknown")
    logger.info("Inbound call from %s", from_number)

    # Simple greeting + record
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello, this is Maxi Bandwidth. Please leave a message after the beep. When you are done, just hang up.</Say>
    <Record maxLength="60" action="/voice/recording-complete" method="POST" playBeep="true" />
</Response>"""
    return twiml(xml)


# --------------------------------------------------------------------
# VOICE: RECORDING CALLBACK
# Twilio: “Recording Status Callback” or Record action -> POST /voice/recording-complete
# --------------------------------------------------------------------
@app.post("/voice/recording-complete")
async def voice_recording_complete(
    RecordingUrl: str = Form(None),
    RecordingDuration: str = Form(None),
    From: str = Form(None),
    To: str = Form(None),
    CallSid: str = Form(None),
