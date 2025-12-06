import os
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from google.oauth2 import service_account
from googleapiclient.discovery import build

from twilio.rest import Client

# Load environment variables from .env
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER,
            GOOGLE_CALENDAR_ID, GOOGLE_SERVICE_ACCOUNT_FILE]):
    raise RuntimeError("Missing required environment variables. Check your .env file.")

# Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Google Calendar service
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=creds)
    return service


class BookingRequest(BaseModel):
    # This is what ElevenLabs/Sunny should send in JSON
    name: str
    phone: str
    address: str
    preferred_date: str  # "YYYY-MM-DD"
    preferred_time: str  # "HH:MM" 24h, local time
    email: str | None = None
    notes: str | None = None


app = FastAPI()


@app.post("/sfnw/book")
async def book_appointment(data: BookingRequest):
    """
    Create a Google Calendar event + SMS confirmation for a SolarFactsNW home visit.
    """

    try:
        # Combine date + time into a datetime object
        start_dt = datetime.strptime(
            f"{data.preferred_date} {data.preferred_time}",
            "%Y-%m-%d %H:%M"
        )
        end_dt = start_dt + timedelta(hours=1)  # assume 1-hour visit

        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()

        # Build calendar event
        event = {
            "summary": f"SolarFactsNW Home Visit – {data.name}",
            "location": data.address,
            "description": (
                f"Name: {data.name}\n"
                f"Phone: {data.phone}\n"
                f"Email: {data.email or 'N/A'}\n"
                f"Notes: {data.notes or ''}\n"
                f"Source: Sunny Watts AI phone agent."
            ),
            "start": {
                "dateTime": start_iso,
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": TIMEZONE,
            },
        }

        service = get_calendar_service()
        created_event = service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID,
            body=event
        ).execute()

        # Nice human-readable time for SMS
        pretty_time = start_dt.strftime("%A, %B %d at %I:%M %p").lstrip("0")

        # Send SMS confirmation in Sunny's "voice"
        sms_body = (
            f"Hi {data.name}, this is Sunny from SolarFactsNW. "
            f"I’ve got you scheduled for your in-home solar visit on "
            f"{pretty_time} at {data.address}. "
            f"If you need to reschedule, just reply to this number."
        )

        # Ensure phone number is in E.164 format; assume ElevenLabs passes correct format
        twilio_client.messages.create(
            to=data.phone,
            from_=TWILIO_FROM_NUMBER,
            body=sms_body
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "event_id": created_event.get("id"),
                "scheduled_start": start_iso,
            },
        )

    except Exception as e:
        # If something goes wrong, tell ElevenLabs it failed
        raise HTTPException(status_code=500, detail=str(e))
