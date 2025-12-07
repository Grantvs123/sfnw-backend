import os
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse, JSONResponse, Response

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

ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "default_agent_id")

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
# Twilio calls this endpoint when an incoming call is received.
# This endpoint connects the call to ElevenLabs AI agent.
# --------------------------------------------------------------------
@app.api_route("/voice/inbound", methods=["GET", "POST"])
async def voice_inbound(request: Request):
    """
    Handle incoming Twilio calls and connect them to ElevenLabs AI agent.
    Accepts both GET and POST requests as Twilio can use either method.
    """
    # Parse form data (Twilio sends call parameters as form data)
    form = await request.form()
    from_number = form.get("From", "Unknown")
    to_number = form.get("To", "Unknown")
    call_sid = form.get("CallSid", "Unknown")
    
    logger.info("Inbound call - From: %s, To: %s, CallSid: %s", from_number, to_number, call_sid)
    
    # TwiML response that connects the call to ElevenLabs
    # Using <Connect> with <Stream> to send audio to ElevenLabs
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://api.elevenlabs.io/v1/convai/conversation?agent_id={ELEVENLABS_AGENT_ID}">
            <Parameter name="call_sid" value="{call_sid}" />
            <Parameter name="from" value="{from_number}" />
        </Stream>
    </Connect>
</Response>"""
    
    return Response(content=xml, media_type="text/xml")


# --------------------------------------------------------------------
# WEBHOOK: ELEVENLABS CALLBACK
# ElevenLabs calls this endpoint after the conversation to send appointment data
# --------------------------------------------------------------------
@app.post("/webhook")
async def webhook(request: Request):
    """
    Handle webhook callbacks from ElevenLabs with appointment data.
    Creates a calendar event based on the appointment information.
    """
    try:
        data = await request.json()
        logger.info("Received webhook from ElevenLabs: %s", json.dumps(data, indent=2))
        
        # Extract appointment details from the webhook payload
        # Adjust these fields based on actual ElevenLabs webhook structure
        summary = data.get("summary", "Appointment from MAXI")
        description = data.get("description", "")
        
        # Create calendar event
        create_calendar_event(summary, description)
        
        return JSONResponse(
            content={"status": "success", "message": "Appointment processed"},
            status_code=200
        )
    except Exception as e:
        logger.error("Error processing webhook: %s", e)
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )


# --------------------------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
