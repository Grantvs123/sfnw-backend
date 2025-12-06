import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import Response, JSONResponse
from dotenv import load_dotenv
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

# Load .env if running locally
load_dotenv()

app = FastAPI()

# ========== ENVIRONMENT VARIABLES ==========
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")

# Just warn if missing — do NOT crash
missing = []
if not TWILIO_ACCOUNT_SID: missing.append("TWILIO_ACCOUNT_SID")
if not TWILIO_AUTH_TOKEN: missing.append("TWILIO_AUTH_TOKEN")
if not TWILIO_FROM_NUMBER: missing.append("TWILIO_FROM_NUMBER")

if missing:
    print("⚠️ WARNING: Missing environment variables:", missing)


# ============================================================
# HEALTH CHECK ENDPOINT
# ============================================================
@app.get("/")
def health():
    return {"status": "running", "message": "Maxi backend is online."}


# ============================================================
# INBOUND CALL HANDLER (Twilio → this endpoint)
# ============================================================
@app.post("/voice/inbound")
async def voice_inbound(request: Request):
    """
    Handles incoming phone calls.
    Twilio POSTs call data here.
    We return TwiML that speaks to the caller.
    """

    vr = VoiceResponse()

    vr.say(
        "Hello, this is Maxi Bandwidth. "
        "Thanks for calling. "
        "Please leave a message after the tone.",
        voice="Polly.Matthew-Neural"
    )

    vr.record(
        maxLength=60,
        action="/voice/recording-complete",
        playBeep=True
    )

    vr.hangup()

    return Response(content=str(vr), media_type="text/xml")


# ============================================================
# RECORDING CALLBACK (Twilio → this endpoint after voicemail)
# ============================================================
@app.post("/voice/recording-complete")
async def recording_complete(
    RecordingUrl: str = Form(None),
    RecordingDuration: str = Form(None),
):
    print("📞 Voicemail received:")
    print("URL:", RecordingUrl)
    print("Duration:", RecordingDuration)

    return JSONResponse({"status": "ok"})


# ============================================================
# INBOUND SMS HANDLER (optional)
# ============================================================
@app.post("/sms/inbound")
async def sms_inbound(request: Request):
    """
    Handles incoming SMS messages.
    """

    form = await request.form()
    body = form.get("Body", "").strip()

    mr = MessagingResponse()
    mr.message(f"Maxi here! You said: {body}")

    return Response(content=str(mr), media_type="text/xml")
