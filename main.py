"""
ElevenLabs Webhook Handler for Maxi Telephony System
Processes incoming voice agent webhooks and creates appointments with notifications
"""

import os
import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Maxi Telephony Webhook Handler",
    description="Handles ElevenLabs voice agent webhooks and processes appointments",
    version="1.0.0"
)

# ============================================================================
# REQUEST MODEL WITH VALIDATION
# ============================================================================

class WebhookPayload(BaseModel):
    """
    ElevenLabs webhook payload model with validation
    """
    caller: str = Field(..., description="Phone number of the caller")
    summary: Optional[str] = Field(None, description="Call summary or notes")
    transcript: Optional[str] = Field(None, description="Full or partial transcript")
    intent: Optional[str] = Field(None, description="Detected intent (e.g., callback, appointment)")
    callback_time: Optional[str] = Field(None, description="ISO 8601 datetime for appointment")
    email: Optional[EmailStr] = Field(None, description="Customer email address")
    customer_name: Optional[str] = Field(None, description="Customer name")
    
    @validator('caller')
    def validate_phone(cls, v):
        """Ensure phone number is in valid format"""
        if not v or len(v) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        # Remove formatting and validate
        digits = ''.join(filter(str.isdigit, v))
        if len(digits) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        return v
    
    @validator('callback_time')
    def validate_datetime(cls, v):
        """Ensure callback_time is valid ISO 8601 datetime"""
        if v:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise ValueError("callback_time must be valid ISO 8601 datetime")
        return v

# ============================================================================
# GOOGLE CALENDAR INTEGRATION
# ============================================================================

def get_calendar_service():
    """
    Initialize and return Google Calendar API service
    Reads base64-encoded service account credentials from environment
    """
    try:
        encoded = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
        if not encoded:
            logger.error("GOOGLE_SERVICE_ACCOUNT_JSON_B64 environment variable not set")
            raise RuntimeError("Google Calendar credentials not configured")
        
        decoded = base64.b64decode(encoded)
        info = json.loads(decoded)
        
        creds = Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        
        service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar service initialized successfully")
        return service
    
    except Exception as e:
        logger.error(f"Failed to initialize Google Calendar service: {str(e)}")
        raise

def create_calendar_event(
    service, 
    customer_name: str,
    phone: str,
    email: Optional[str],
    callback_time: str,
    summary: str,
    transcript: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Create a calendar event for the appointment
    
    Args:
        service: Google Calendar API service
        customer_name: Name of the customer
        phone: Customer phone number
        email: Customer email (optional)
        callback_time: ISO 8601 datetime string
        summary: Call summary
        transcript: Full transcript (optional)
    
    Returns:
        Created event object or None if failed
    """
    try:
        calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
        
        # Parse the callback time
        start_time = datetime.fromisoformat(callback_time.replace('Z', '+00:00'))
        # Default 30-minute appointment
        end_time = start_time + timedelta(minutes=30)
        
        # Build detailed description
        description_parts = [
            f"Customer: {customer_name}",
            f"Phone: {phone}",
        ]
        if email:
            description_parts.append(f"Email: {email}")
        description_parts.append(f"\nSummary:\n{summary}")
        if transcript:
            description_parts.append(f"\n\nTranscript:\n{transcript}")
        
        event = {
            "summary": f"Appointment: {customer_name}",
            "description": "\n".join(description_parts),
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "America/New_York",  # Adjust as needed
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "America/New_York",
            },
            "attendees": [],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},  # 1 day before
                    {"method": "popup", "minutes": 30},  # 30 min before
                ],
            },
        }
        
        # Add customer email as attendee if provided
        if email:
            event["attendees"].append({"email": email})
        
        created_event = service.events().insert(
            calendarId=calendar_id, 
            body=event,
            sendUpdates="all"  # Send email notifications to attendees
        ).execute()
        
        logger.info(f"Calendar event created successfully: {created_event.get('id')}")
        logger.info(f"Event link: {created_event.get('htmlLink')}")
        
        return created_event
    
    except HttpError as e:
        logger.error(f"Google Calendar API error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Failed to create calendar event: {str(e)}")
        return None

# ============================================================================
# TWILIO SMS INTEGRATION
# ============================================================================

# Initialize Twilio client
TWILIO_SID = os.environ.get("TWILIO_SID", "")
TWILIO_AUTH = os.environ.get("TWILIO_AUTH", "")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER", "")

twilio_client = None
if TWILIO_SID and TWILIO_AUTH:
    try:
        twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
        logger.info("Twilio client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {str(e)}")
else:
    logger.warning("Twilio credentials not configured - SMS notifications disabled")

def send_sms(to: str, message: str) -> bool:
    """
    Send SMS confirmation via Twilio
    
    Args:
        to: Recipient phone number
        message: SMS message body
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not twilio_client or not TWILIO_NUMBER:
        logger.warning("Twilio not configured - skipping SMS")
        return False
    
    try:
        message_obj = twilio_client.messages.create(
            to=to,
            from_=TWILIO_NUMBER,
            body=message,
        )
        logger.info(f"SMS sent successfully to {to} (SID: {message_obj.sid})")
        return True
    
    except TwilioRestException as e:
        logger.error(f"Twilio API error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send SMS: {str(e)}")
        return False

def format_sms_message(customer_name: str, callback_time: str, summary: str) -> str:
    """
    Format a professional SMS confirmation message
    
    Args:
        customer_name: Customer name
        callback_time: ISO 8601 datetime string
        summary: Appointment summary
    
    Returns:
        Formatted SMS message
    """
    try:
        dt = datetime.fromisoformat(callback_time.replace('Z', '+00:00'))
        formatted_date = dt.strftime("%A, %B %d at %I:%M %p")
        
        message = f"""Hi {customer_name}!

Your appointment has been confirmed for {formatted_date}.

Details: {summary}

Reply CONFIRM to acknowledge or call us if you need to reschedule.

- Maxi Team"""
        
        return message
    except Exception as e:
        logger.error(f"Failed to format SMS message: {str(e)}")
        return f"Hi {customer_name}! Your appointment has been scheduled. We'll see you soon!"

# ============================================================================
# EMAIL INTEGRATION
# ============================================================================

EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

if EMAIL_FROM and EMAIL_PASSWORD:
    logger.info("Email service configured successfully")
else:
    logger.warning("Email credentials not configured - email notifications disabled")

def send_email(to: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """
    Send email confirmation
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        logger.warning("Email not configured - skipping email")
        return False
    
    try:
        # Create multipart message
        msg = MIMEMultipart("alternative")
        msg["From"] = EMAIL_FROM
        msg["To"] = to
        msg["Subject"] = subject
        
        # Attach plain text version
        msg.attach(MIMEText(body, "plain"))
        
        # Attach HTML version if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, to, msg.as_string())
        
        logger.info(f"Email sent successfully to {to}")
        return True
    
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def format_email_body(
    customer_name: str,
    callback_time: str,
    summary: str,
    phone: str,
    calendar_link: Optional[str] = None
) -> tuple[str, str]:
    """
    Format professional email confirmation (plain text and HTML)
    
    Args:
        customer_name: Customer name
        callback_time: ISO 8601 datetime string
        summary: Appointment summary
        phone: Customer phone
        calendar_link: Optional Google Calendar event link
    
    Returns:
        Tuple of (plain_text_body, html_body)
    """
    try:
        dt = datetime.fromisoformat(callback_time.replace('Z', '+00:00'))
        formatted_date = dt.strftime("%A, %B %d, %Y")
        formatted_time = dt.strftime("%I:%M %p %Z")
        
        # Plain text version
        plain_text = f"""Hello {customer_name},

This email confirms your appointment with Maxi.

Appointment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date: {formatted_date}
Time: {formatted_time}
Phone: {phone}

Summary:
{summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        if calendar_link:
            plain_text += f"View in Google Calendar: {calendar_link}\n\n"
        
        plain_text += """If you need to reschedule or cancel, please contact us as soon as possible.

We look forward to speaking with you!

Best regards,
The Maxi Team

---
This is an automated confirmation. Please do not reply to this email.
"""
        
        # HTML version
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .content {{ background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; }}
        .details-box {{ background: #f8f9fa; border-left: 4px solid #667eea; padding: 20px; margin: 20px 0; border-radius: 5px; }}
        .detail-row {{ margin: 10px 0; }}
        .detail-label {{ font-weight: bold; color: #667eea; display: inline-block; width: 80px; }}
        .summary-box {{ background: #fff9e6; border: 1px solid #ffd966; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        .button:hover {{ background: #5568d3; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; border-radius: 0 0 10px 10px; border: 1px solid #e0e0e0; border-top: none; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>✓ Appointment Confirmed</h1>
    </div>
    <div class="content">
        <p>Hello <strong>{customer_name}</strong>,</p>
        <p>This email confirms your appointment with Maxi.</p>
        
        <div class="details-box">
            <h3 style="margin-top: 0; color: #667eea;">📅 Appointment Details</h3>
            <div class="detail-row">
                <span class="detail-label">Date:</span> {formatted_date}
            </div>
            <div class="detail-row">
                <span class="detail-label">Time:</span> {formatted_time}
            </div>
            <div class="detail-row">
                <span class="detail-label">Phone:</span> {phone}
            </div>
        </div>
        
        <div class="summary-box">
            <h4 style="margin-top: 0;">📋 Summary</h4>
            <p style="margin-bottom: 0;">{summary}</p>
        </div>
        """
        
        if calendar_link:
            html += f"""
        <div style="text-align: center;">
            <a href="{calendar_link}" class="button">📅 View in Google Calendar</a>
        </div>
        """
        
        html += """
        <p style="margin-top: 30px;">If you need to reschedule or cancel, please contact us as soon as possible.</p>
        <p>We look forward to speaking with you!</p>
        <p style="margin-top: 20px;"><strong>Best regards,</strong><br>The Maxi Team</p>
    </div>
    <div class="footer">
        This is an automated confirmation. Please do not reply to this email.
    </div>
</body>
</html>"""
        
        return plain_text, html
    
    except Exception as e:
        logger.error(f"Failed to format email: {str(e)}")
        # Return simple fallback
        plain = f"Hello {customer_name},\n\nYour appointment has been confirmed.\n\nBest regards,\nMaxi Team"
        return plain, plain

# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - basic info"""
    return {
        "service": "Maxi Telephony Webhook Handler",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "webhook": "/webhook"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    services_status = {
        "google_calendar": bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")),
        "twilio_sms": bool(twilio_client and TWILIO_NUMBER),
        "email": bool(EMAIL_FROM and EMAIL_PASSWORD),
    }
    
    all_healthy = all(services_status.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": services_status,
    }

@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Main webhook endpoint for ElevenLabs voice agent
    
    Processes incoming webhook payload and:
    1. Validates the data
    2. Creates Google Calendar event
    3. Sends SMS confirmation
    4. Sends email confirmation
    
    Returns appropriate status codes to ElevenLabs
    """
    try:
        # Parse and validate request body
        raw_data = await request.json()
        logger.info(f"Received webhook from {request.client.host}: {json.dumps(raw_data, indent=2)}")
        
        # Validate payload with Pydantic
        try:
            payload = WebhookPayload(**raw_data)
        except Exception as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payload: {str(e)}"
            )
        
        # Extract data
        customer_name = payload.customer_name or "Valued Customer"
        phone = payload.caller
        email = payload.email
        callback_time = payload.callback_time
        summary = payload.summary or "Appointment scheduled via phone"
        transcript = payload.transcript
        intent = payload.intent or "appointment"
        
        # Response tracking
        responses = {
            "calendar_created": False,
            "sms_sent": False,
            "email_sent": False,
            "calendar_event_id": None,
            "calendar_link": None,
        }
        
        # If no callback time specified, log and return early
        if not callback_time:
            logger.warning("No callback_time provided - skipping appointment creation")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "acknowledged",
                    "message": "Webhook received but no appointment time specified",
                    "data": responses
                }
            )
        
        # 1. Create Google Calendar Event
        logger.info(f"Creating calendar event for {customer_name} at {callback_time}")
        try:
            calendar_service = get_calendar_service()
            event = create_calendar_event(
                service=calendar_service,
                customer_name=customer_name,
                phone=phone,
                email=email,
                callback_time=callback_time,
                summary=summary,
                transcript=transcript
            )
            
            if event:
                responses["calendar_created"] = True
                responses["calendar_event_id"] = event.get("id")
                responses["calendar_link"] = event.get("htmlLink")
                logger.info(f"✓ Calendar event created: {event.get('id')}")
            else:
                logger.error("Failed to create calendar event")
        
        except Exception as e:
            logger.error(f"Calendar creation failed: {str(e)}")
            # Continue to notifications even if calendar fails
        
        # 2. Send SMS Confirmation
        if phone:
            logger.info(f"Sending SMS confirmation to {phone}")
            try:
                sms_message = format_sms_message(customer_name, callback_time, summary)
                sms_sent = send_sms(phone, sms_message)
                responses["sms_sent"] = sms_sent
                if sms_sent:
                    logger.info(f"✓ SMS sent to {phone}")
                else:
                    logger.warning(f"SMS failed to send to {phone}")
            except Exception as e:
                logger.error(f"SMS sending failed: {str(e)}")
        
        # 3. Send Email Confirmation
        if email:
            logger.info(f"Sending email confirmation to {email}")
            try:
                plain_body, html_body = format_email_body(
                    customer_name=customer_name,
                    callback_time=callback_time,
                    summary=summary,
                    phone=phone,
                    calendar_link=responses.get("calendar_link")
                )
                
                email_sent = send_email(
                    to=email,
                    subject=f"Appointment Confirmation - {customer_name}",
                    body=plain_body,
                    html_body=html_body
                )
                responses["email_sent"] = email_sent
                if email_sent:
                    logger.info(f"✓ Email sent to {email}")
                else:
                    logger.warning(f"Email failed to send to {email}")
            except Exception as e:
                logger.error(f"Email sending failed: {str(e)}")
        
        # Success response
        logger.info(f"Webhook processed successfully: {json.dumps(responses, indent=2)}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "Appointment processed successfully",
                "data": responses,
                "customer": {
                    "name": customer_name,
                    "phone": phone,
                    "email": email,
                },
                "appointment_time": callback_time,
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error processing webhook: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 60)
    logger.info("Maxi Telephony Webhook Handler Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'development')}")
    logger.info(f"Google Calendar: {'✓ Configured' if os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON_B64') else '✗ Not configured'}")
    logger.info(f"Twilio SMS: {'✓ Configured' if twilio_client and TWILIO_NUMBER else '✗ Not configured'}")
    logger.info(f"Email: {'✓ Configured' if EMAIL_FROM and EMAIL_PASSWORD else '✗ Not configured'}")
    logger.info("=" * 60)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
