from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse

app = FastAPI()

def twiml(xml: str):
    return PlainTextResponse(xml, media_type="application/xml")

# ----------------------------------------------------
# HEALTH CHECK
# ----------------------------------------------------
@app.get("/status")
def status():
    return {"status": "running", "message": "Maxi backend is online."}

# ----------------------------------------------------
# VOICE INBOUND
# ----------------------------------------------------
@app.post("/voice/inbound")
@app.get("/voice/inbound")
async def voice_inbound():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello, this is Maxi Bandwidth. How can I help you today?</Say>
    <Record maxLength="30" action="/voice/recorded" />
</Response>
"""
    return twiml(xml)

# ----------------------------------------------------
# RECORDING CALLBACK
# ----------------------------------------------------
@app.post("/voice/recorded")
async def voice_recorded(RecordingUrl: str = Form(...)):
    print("Recording received:", RecordingUrl)
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Thank you. Maxi will get back to you shortly.</Say>
</Response>
"""
    return twiml(xml)

# ----------------------------------------------------
# SMS HANDLER
# ----------------------------------------------------
@app.post("/sms/inbound")
@app.get("/sms/inbound")
async def sms_inbound(From: str = "", Body: str = ""):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Maxi here! You said: {Body}</Message>
</Response>
"""
    return twiml(xml)
