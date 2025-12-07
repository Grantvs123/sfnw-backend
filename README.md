# SFNW Backend - MAXI AI Phone System

Backend service for MAXI, an AI-powered phone system that handles incoming calls using ElevenLabs conversational AI and manages appointments via Google Calendar.

## Features

- **Incoming Call Handling**: Connects Twilio calls to ElevenLabs AI agent for natural conversation
- **Appointment Management**: Receives appointment data from ElevenLabs and creates Google Calendar events
- **Health Monitoring**: Built-in health check and status endpoints

## API Endpoints

### `/voice/inbound` (GET/POST)
Handles incoming Twilio calls and connects them to the ElevenLabs AI agent.

**Called by**: Twilio when an incoming call is received

**Parameters** (sent by Twilio as form data):
- `From`: Caller's phone number
- `To`: Called phone number
- `CallSid`: Unique call identifier

**Response**: TwiML XML that establishes a WebSocket stream to ElevenLabs

**Example TwiML Response**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://api.elevenlabs.io/v1/convai/conversation?agent_id=YOUR_AGENT_ID">
            <Parameter name="call_sid" value="CA123..." />
            <Parameter name="from" value="+1234567890" />
        </Stream>
    </Connect>
</Response>
```

### `/webhook` (POST)
Receives appointment data from ElevenLabs after a conversation and creates a Google Calendar event.

**Called by**: ElevenLabs after a conversation completes

**Request Body**: JSON with appointment details

**Response**: JSON with status

### `/health` (GET)
Health check endpoint for monitoring.

**Response**:
```json
{
    "status": "healthy",
    "timestamp": "2025-12-07T..."
}
```

### `/status` (GET)
Service status endpoint.

**Response**:
```json
{
    "status": "running",
    "message": "Maxi backend is online."
}
```

### `/version` (GET)
Returns the current version of the service.

**Response**:
```json
{
    "version": "1.0.0"
}
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|----------|
| `TWILIO_ACCOUNT_SID` | Your Twilio Account SID | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN` | Your Twilio Auth Token | `your_auth_token_here` |
| `TWILIO_FROM_NUMBER` | Your Twilio phone number | `+1234567890` |
| `ELEVENLABS_AGENT_ID` | ElevenLabs AI Agent ID | `your_agent_id_here` |
| `GOOGLE_CALENDAR_ID` | Google Calendar ID (usually your email) | `your_email@gmail.com` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Service Account credentials (JSON string) | `'{"type":"service_account",...}'` |

### Optional

| Variable | Description | Default |
|----------|-------------|----------|
| `TIMEZONE` | Timezone for calendar events (IANA format) | `America/Los_Angeles` |

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Grantvs123/sfnw-backend.git
   cd sfnw-backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

4. **Run the service**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Twilio Configuration

1. Go to your [Twilio Console](https://console.twilio.com/)
2. Navigate to your phone number settings
3. Under "Voice & Fax", set the webhook for incoming calls:
   - **A CALL COMES IN**: `https://your-domain.com/voice/inbound` (HTTP POST)

## ElevenLabs Configuration

1. Create an AI agent in the [ElevenLabs Dashboard](https://elevenlabs.io/)
2. Copy your Agent ID
3. Configure the webhook URL in ElevenLabs to point to: `https://your-domain.com/webhook`

## Google Calendar Setup

1. Create a service account in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Calendar API
3. Download the service account JSON key
4. Share your Google Calendar with the service account email
5. Set the JSON content as the `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable

## Deployment

This service is designed to be deployed on Railway, Heroku, or any platform that supports Python web applications.

### Railway Deployment

1. Connect your GitHub repository to Railway
2. Set all required environment variables in Railway dashboard
3. Railway will automatically deploy on push to main branch

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Logging

The service logs important events including:
- Incoming call details (From, To, CallSid)
- Webhook payloads from ElevenLabs
- Calendar event creation
- Errors and warnings

## License

MIT
