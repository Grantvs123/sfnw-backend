import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from twilio.rest import Client
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------------------------------------------------------
#  ENVIRONMENT VARIABLES
# ---------------------------------------------------------

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")  # optional
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")
GRANT1_NUMBER = os.getenv("GRANT1_NUMBER", "")

# ---------------------------------------------------------
#  SAFE CHECK: DO NOT CRASH IF VARIABLES MISSING
# ---------------------------------------------------------

missing = []

if not TWILIO_ACCOUNT_SID:
    missing.append("TWILIO_ACCOUNT_SID")

if not TWILIO_AUTH_TOKEN:
    missing.append("TWILIO_AUTH_TOKEN")

if not TWILIO_FROM_NUMBER:
    missing.append("TWILIO_FROM_NUMBER")

if not GOOGLE_CALENDAR_ID:
    missing.append("GOOGLE_CALENDAR_ID")

# Service account must come from either JSON or FILE
if not GOOGLE_SERVICE_ACCOUNT_FILE and not GOOGLE_SERVICE_ACCOUNT_JSON:
    missing.append("GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON")

if missing:
    print("⚠️ WARNING: Missing environment variables:", missing)

# ---------------------------------------------------------
#  INITIALIZE TWILIO CLIENT (won’t crash if creds missing)
# ---------------------------------------------------------

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ---------------------------------------------------------
#  GOOGLE CALENDAR SERVICE ACCOUNT LOADING
# ---------------------------------------------------------

def load_google_credentials():
    """
    Loads Google credentials from either:
    - RAW JSON string (Railway recommended)
    - A file path (optional)
    """

    if GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            data = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
            credentials = service_account.Credentials.from_service_account_info(
                data,
                scopes=["https://www.googleapis.com/auth/calendar"]
            )
            return credentials
        except Exception as e:
            print("❌ Failed to load GOOGLE_SERVICE_ACCOUNT_JSON:", e)

    if GOOGLE_SERVICE_ACCOUNT_FILE:
        try:
            credentials = service_account.Credentials.from_service_account_file(
                GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=["https://www.googleapis.com/auth/calendar"]
            )
            return credentials
        except Exception as e:
            print("❌ Failed to load GOOGLE_SERVICE_ACCOUNT_FILE:", e)

    print("⚠️ No valid Google credentials available.")
    return None


# ---------------------------------------------------------
#  FASTAPI SETUP
# ---------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------------------------------------------------------
#  REQUEST MODEL FOR BOOKING
# ---------------------------------------------------------

class BookingRequest(BaseModel):
    caller_name: str = ""
    caller_phone: str = ""
    start_iso: str
    end_iso: str
    notes: str = ""

# ---------------------------------------------------------
#  BOOKING ENDPOINT
# ---------------------------------------------------------

@app.post("/maxi/book")
def book_appointment(data: BookingRequest):
    print("📩 Booking request received:", data.dict())

    # Load credentials
    credentials = load_google_credentials()
    if not credentials:
        raise HTTPException(status_code=500, detail="Google credentials missing.")

    try:
        service = build("calendar", "v3", credentials=credentials)

        event_body = {
            "summary": f"Callback with {data.caller_name or 'Caller'}",
            "description": f"Phone: {data.caller_phone}\nNotes: {data.notes}",
            "start": {"dateTime": data.start_iso, "timeZone": TIMEZONE},
            "end": {"dateTime": data.end_iso, "timeZone": TIMEZONE},
        }

        event = service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID,
            body=event_body
        ).execute()

        print("✅ Google Calendar event created:", event.get("id"))

        # ---------------------------------------------------------
        #  SMS to caller (if provided)
        # ---------------------------------------------------------
        if data.caller_phone:
            try:
                twilio_client.messages.create(
                    to=data.caller_phone,
                    from_=TWILIO_FROM_NUMBER,
                    body=f"Your appointment is scheduled for {data.start_iso}."
                )
                print("📲 Sent SMS to caller.")
            except Exception as e:
                print("❌ Failed to send SMS to caller:", e)

        # ---------------------------------------------------------
        #  SMS to Grant1 (notification)
        # ---------------------------------------------------------
        if GRANT1_NUMBER:
            try:
                twilio_client.messages.create(
                    to=GRANT1_NUMBER,
                    from_=TWILIO_FROM_NUMBER,
                    body=f"Maxi booked a callback with {data.caller_name} ({data.caller_phone}) at {data.start_iso}."
                )   
                print("📲 Sent SMS to Grant1.")
            except Exception as e:
                print("❌ Failed to notify Grant1:", e)

        return {"status": "ok", "eventId": event.get("id")}

    except Exception as e:
        print("❌ Booking failed:", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
#  ROOT CHECK
# ---------------------------------------------------------

@app.get("/")
def root():
    return {"status": "running", "message": "Maxi backend is online."}
