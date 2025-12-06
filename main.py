import os
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from twilio.rest import Client
from google.oauth2 import service_account
from googleapiclient.discovery import build

# -------------------------------------------------------
# ENVIRONMENT VARIABLES
# -------------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

# -------------------------------------------------------
# WARN IF VARIABLES ARE MISSING
# -------------------------------------------------------
missing = []
if not TWILIO_ACCOUNT_SID: missing.append("TWILIO_ACCOUNT_SID")
if not TWILIO_AUTH_TOKEN: missing.append("TWILIO_AUTH_TOKEN")
if not TWILIO_FROM_NUMBER: missing.append("TWILIO_FROM_NUMBER")
if not GOOGLE_CALENDAR_ID: missing.append("GOOGLE_CALENDAR_ID")
if not GOOGLE_SERVICE_ACCOUNT_FILE and not GOOGLE_SERVICE_ACCOUNT_JSON:
    missing.append("GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON")

if missing:
    print("⚠️ WARNING: Missing environment variables:", missing)

# -------------------------------------------------------
# LOAD TWILIO
# -------------------------------------------------------
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# -------------------------------------------------------
# LOAD GOOGLE CALENDAR SERVICE
# -------------------------------------------------------
def load_calendar_service():
    try:
        if GOOGLE_SERVICE_ACCOUNT_JSON:
            info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
            creds = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/calendar"]
            )
        else:
            creds = service_account.Credentials.from_service_account_file(
                GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=["https://www.googleapis.com/auth/calendar"]
            )

        return build("calendar", "v3", credentials=creds)

    except Exception as e:
        print("❌ Google Calendar error:", e)
        return None

calendar_service = load_calendar_service()

# -------------------------------------------------------
# FASTAPI APP
# -------------------------------------------------------
app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "running", "message": "Maxi backend is online."}

# -------------------------------------------------------
# CREATE CALENDAR EVENT
# -------------------------------------------------------
def create_event(start_time, caller_number):
    if not calendar_service:
        print("❌ Calendar service unavailable.")
        return None

    end_time = start_time + timedelta(minutes=30)

    event_body = {
        "summary": f"Callback Request from {caller_number}",
        "description": "Auto-scheduled by Maxi Appointment System",
        "start": {"dateTime": start_time.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_time.isoformat(), "timeZone": TIMEZONE},
    }

    try:
        event = calendar_service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID,
            body=event_body
        ).execute()
        return event
    except Exception as e:
        print("❌ Calendar insertion error:", e)
        return None

# -------------------------------------------------------
# TWILIO INCOMING WEBHOOK
# -------------------------------------------------------
@app.post("/incoming")
async def incoming_sms(request: Request):
    """Handles incoming calls or SMS from Twilio."""
    if not twilio_client:
        raise HTTPException(500, "Twilio not configured")

    form = await request.form()
    from_number = form.get("From")
    body = form.get("Body", "").strip().lower()

    print(f"📩 Incoming from {from_number}: {body}")

    # Simple intent handler
    if "callback" in body or "call back" in body:
        start_time = datetime.now() + timedelta(minutes=15)
        event = create_event(start_time, from_number)

        if event:
            twilio_client.messages.create(
                to=from_number,
                from_=TWILIO_FROM_NUMBER,
                body=f"You're booked! A specialist will call you at {start_time.strftime('%I:%M %p')}."
            )
            return JSONResponse({"status": "booked"})

        return JSONResponse({"status": "failed"}, status_code=500)

    # Default reply
    twilio_client.messages.create(
        to=from_number,
        from_=TWILIO_FROM_NUMBER,
        body="Hello! Reply 'callback' to schedule a return call."
    )

    return JSONResponse({"status": "ok"})

# -------------------------------------------------------
# ROOT MESSAGE
# -------------------------------------------------------
@app.get("/")
def home():
    return {"message": "Maxi backend operational. Use /health to test."}
