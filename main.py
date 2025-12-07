from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse
import os

app = FastAPI()

# ============================================================
# Helper to return TwiML with correct Content-Type
# ============================================================
def twiml(xml: str):
    return PlainTextResponse(xml, media_type="application/xml")

# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/status")
def status():
    return {"status": "running", "message": "Maxi backend is online."}

# ============================================================
# VOICE — INBOUND CALL HANDLER
# ============================================================
@app.post("/voice/inbound")
async def voice_inbound():
    xml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say voice="alice">Hello, this is Maxi Bandwidth. How can I help you today?</Say>
        <Pause length="1"/>
        <Say voice="alice">Please speak after the beep.</Say>
        <Record maxLength="30" action="/voice/recorded" />
    </Response>
    """
    return twiml(xml)

# ============================================================
# VOICE — RECORDING CALLBACK
# ============================================================
@app.post("/voice/recorded")
async def voice_recorded(RecordingUrl: str = Form(...)):
    print("Recording received:", RecordingUrl)
    xml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say voice="alice">Thank you. Maxi will get back to you shortly.</Say>
    </Response>
    """
    return twiml(xml)

# ============================================================
# SMS HANDLER
# Twilio hits this when someone texts your number
# ============================================================
@app.post("/incoming")
async def incoming_sms(Body: str = Form(...)):
    reply = f"Maxi here! You said: {Body}"
    xml = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Message>{reply}</Message>
    </Response>
    """
    return twiml(xml)

# ============================================================
# VERSION CHECK
# ============================================================
@app.get("/version")
def version():
    return {"version": "3.14"}
