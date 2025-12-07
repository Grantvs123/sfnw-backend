# Maxi Telephony Webhook Handler

A production-ready webhook handler for ElevenLabs voice agent integrations. Automatically processes voice calls, creates Google Calendar appointments, and sends SMS/Email confirmations.

## 🌟 Features

- **ElevenLabs Integration**: Receives and processes voice agent webhooks
- **Google Calendar**: Automatically creates calendar events with detailed information
- **SMS Notifications**: Sends professional confirmation messages via Twilio
- **Email Confirmations**: Sends beautiful HTML email confirmations
- **Data Validation**: Robust input validation using Pydantic
- **Error Handling**: Comprehensive error handling and logging
- **Health Monitoring**: Built-in health check endpoint
- **Production Ready**: Designed for deployment on Railway or similar platforms

## 📋 Requirements

- Python 3.9+
- Google Cloud service account with Calendar API access
- Twilio account (for SMS)
- SMTP email account (Gmail recommended)
- Railway account (or similar PaaS)

## 🚀 Quick Start

### 1. Clone or Download This Repository

```bash
cd maxi_telephony_handler
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials (see Configuration section below).

### 4. Run Locally for Testing

```bash
uvicorn main:app --reload --port 8000
```

The service will be available at `http://localhost:8000`

### 5. Test the Health Endpoint

```bash
curl http://localhost:8000/health
```

## ⚙️ Configuration

### Required Environment Variables

#### Google Calendar Configuration

1. **Create a Google Cloud Service Account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google Calendar API
   - Create a Service Account
   - Generate a JSON key file

2. **Prepare the Service Account JSON**:
   ```bash
   # Encode your service account JSON to base64
   base64 -i service-account.json | tr -d '\n' > encoded.txt
   ```

3. **Set Environment Variable**:
   ```bash
   GOOGLE_SERVICE_ACCOUNT_JSON_B64=<paste the base64 encoded string>
   ```

4. **Share Calendar with Service Account**:
   - Open Google Calendar
   - Click settings (gear icon) → Settings
   - Select the calendar you want to use
   - Scroll to "Share with specific people"
   - Add the service account email (found in your JSON file: `client_email`)
   - Give "Make changes to events" permission

5. **Get Calendar ID** (optional, defaults to "primary"):
   - In Google Calendar settings
   - Select your calendar
   - Scroll to "Integrate calendar"
   - Copy the Calendar ID
   ```bash
   GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
   ```

#### Twilio SMS Configuration

1. **Sign up at [Twilio](https://www.twilio.com/)**
2. **Get your credentials**:
   - Account SID
   - Auth Token
   - Phone Number

3. **Set Environment Variables**:
   ```bash
   TWILIO_SID=your_account_sid
   TWILIO_AUTH=your_auth_token
   TWILIO_NUMBER=+1234567890
   ```

#### Email Configuration (Gmail Example)

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account → Security
   - Select "2-Step Verification"
   - Scroll to "App passwords"
   - Generate password for "Mail"

3. **Set Environment Variables**:
   ```bash
   EMAIL_FROM=your-email@gmail.com
   EMAIL_PASSWORD=your-app-password
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   ```

### Optional Environment Variables

```bash
# Environment identifier (for logging)
ENVIRONMENT=production

# Port (Railway sets this automatically)
PORT=8000
```

## 🚂 Deploy to Railway

### Step 1: Prepare Your Repository

1. Initialize git repository (if not already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Push to GitHub/GitLab:
   ```bash
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

### Step 2: Deploy on Railway

1. **Sign up/Login** to [Railway](https://railway.app/)

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Authorize Railway to access your repository
   - Select your repository

3. **Configure Environment Variables**:
   - Go to your project
   - Click on your service
   - Go to "Variables" tab
   - Add all required environment variables:
     ```
     GOOGLE_SERVICE_ACCOUNT_JSON_B64
     GOOGLE_CALENDAR_ID
     TWILIO_SID
     TWILIO_AUTH
     TWILIO_NUMBER
     EMAIL_FROM
     EMAIL_PASSWORD
     SMTP_SERVER
     SMTP_PORT
     ENVIRONMENT
     ```

4. **Deploy**:
   - Railway will automatically detect the Procfile
   - Build and deployment will start automatically
   - Wait for deployment to complete

5. **Get Your Webhook URL**:
   - Go to "Settings" tab
   - Find "Domains" section
   - Copy the generated URL (e.g., `https://your-app.railway.app`)
   - Your webhook endpoint will be: `https://your-app.railway.app/webhook`

### Step 3: Test Your Deployment

```bash
# Test health endpoint
curl https://your-app.railway.app/health

# Test webhook with sample data
curl -X POST https://your-app.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "caller": "+1234567890",
    "customer_name": "John Doe",
    "summary": "Customer wants to schedule a callback",
    "callback_time": "2025-12-08T15:00:00Z",
    "email": "john@example.com",
    "intent": "appointment"
  }'
```

## 🎙️ Configure ElevenLabs Webhook

### In ElevenLabs Voice Agent Dashboard:

1. **Navigate to Your Voice Agent**:
   - Log in to [ElevenLabs](https://elevenlabs.io/)
   - Go to Voice Agents section
   - Select your agent

2. **Configure Webhook URL**:
   - Find "Webhook" or "Callback URL" settings
   - Enter your Railway webhook URL:
     ```
     https://your-app.railway.app/webhook
     ```
   - Set method to `POST`
   - Set content type to `application/json`

3. **Configure Payload**:
   - Ensure your voice agent sends the following fields:
     ```json
     {
       "caller": "string (phone number)",
       "customer_name": "string (optional)",
       "summary": "string",
       "transcript": "string (optional)",
       "intent": "string (optional)",
       "callback_time": "string (ISO 8601 datetime)",
       "email": "string (optional, valid email)"
     }
     ```

4. **Test the Integration**:
   - Make a test call to your voice agent
   - Check Railway logs to verify webhook was received
   - Verify calendar event was created
   - Check SMS and email were sent

## 🧪 Testing

### Local Testing with Sample Payload

Create a test file `test_webhook.py`:

```python
import requests
import json
from datetime import datetime, timedelta

# Calculate tomorrow at 3 PM
tomorrow = datetime.now() + timedelta(days=1)
appointment_time = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)

payload = {
    "caller": "+1234567890",
    "customer_name": "Jane Smith",
    "summary": "Customer needs consultation about our services",
    "transcript": "Hi, I'd like to schedule a call to discuss your product offerings...",
    "intent": "appointment",
    "callback_time": appointment_time.isoformat() + "Z",
    "email": "jane.smith@example.com"
}

# Change to your actual URL
url = "http://localhost:8000/webhook"
# url = "https://your-app.railway.app/webhook"

response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
```

Run the test:

```bash
python test_webhook.py
```

### Using curl

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "caller": "+1234567890",
    "customer_name": "Test User",
    "summary": "Test appointment",
    "callback_time": "2025-12-08T15:00:00Z",
    "email": "test@example.com"
  }'
```

## 📊 Monitoring

### Health Check Endpoint

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-07T12:00:00",
  "services": {
    "google_calendar": true,
    "twilio_sms": true,
    "email": true
  }
}
```

### View Logs in Railway

1. Go to your Railway project
2. Click on your service
3. Go to "Deployments" tab
4. Click on the latest deployment
5. View logs in real-time

### Log Levels

- `INFO`: Normal operation events
- `WARNING`: Degraded service (e.g., SMS not configured)
- `ERROR`: Failed operations (with details)

## 🔧 Troubleshooting

### Calendar Events Not Creating

1. **Check service account permissions**:
   - Verify the calendar is shared with the service account email
   - Ensure "Make changes to events" permission is granted

2. **Verify base64 encoding**:
   ```bash
   echo $GOOGLE_SERVICE_ACCOUNT_JSON_B64 | base64 -d | jq .
   ```
   Should output valid JSON.

3. **Check Calendar ID**:
   - Verify `GOOGLE_CALENDAR_ID` matches your calendar
   - Or remove it to use "primary" calendar

### SMS Not Sending

1. **Verify Twilio credentials**:
   - Check Account SID and Auth Token
   - Ensure phone number is in E.164 format: `+1234567890`

2. **Check phone number verification**:
   - For trial accounts, verify recipient numbers in Twilio console

3. **Review Twilio logs**:
   - Log in to Twilio console
   - Check message logs for errors

### Email Not Sending

1. **For Gmail users**:
   - Ensure 2FA is enabled
   - Use App Password, not regular password
   - Check "Less secure app access" is not required (use App Password instead)

2. **For other providers**:
   - Verify SMTP server and port
   - Check if TLS/SSL is required

3. **Test SMTP connection**:
   ```python
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('your-email@gmail.com', 'your-app-password')
   print("SMTP connection successful!")
   server.quit()
   ```

### Webhook Receiving 400/500 Errors

1. **Validate payload format**:
   - Ensure `caller` field is present and valid
   - Verify `callback_time` is ISO 8601 format
   - Check `email` is valid email format (if provided)

2. **Check logs** for specific error messages

3. **Test with minimal payload**:
   ```json
   {
     "caller": "+1234567890",
     "callback_time": "2025-12-08T15:00:00Z"
   }
   ```

## 📁 Project Structure

```
maxi_telephony_handler/
├── main.py              # Main application code
├── requirements.txt     # Python dependencies
├── Procfile            # Railway deployment config
├── .env.example        # Environment variables template
├── README.md           # This file
└── test_webhook.py     # Testing script (create this)
```

## 🔐 Security Best Practices

1. **Never commit `.env` file** to version control
2. **Use environment variables** for all sensitive data
3. **Rotate credentials regularly**
4. **Use HTTPS** for webhook URLs (Railway provides this)
5. **Validate webhook signatures** (add if ElevenLabs supports it)
6. **Monitor logs** for suspicious activity
7. **Limit service account permissions** to only what's needed

## 🤝 Contributing

To improve this webhook handler:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 API Documentation

### POST /webhook

Processes ElevenLabs voice agent webhooks.

**Request Body**:
```json
{
  "caller": "string (required, phone number)",
  "customer_name": "string (optional)",
  "summary": "string (optional)",
  "transcript": "string (optional)",
  "intent": "string (optional)",
  "callback_time": "string (required, ISO 8601 datetime)",
  "email": "string (optional, valid email)"
}
```

**Success Response** (200):
```json
{
  "status": "success",
  "message": "Appointment processed successfully",
  "data": {
    "calendar_created": true,
    "sms_sent": true,
    "email_sent": true,
    "calendar_event_id": "event123",
    "calendar_link": "https://calendar.google.com/..."
  },
  "customer": {
    "name": "John Doe",
    "phone": "+1234567890",
    "email": "john@example.com"
  },
  "appointment_time": "2025-12-08T15:00:00Z"
}
```

**Error Response** (400/500):
```json
{
  "detail": "Error message describing what went wrong"
}
```

### GET /health

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-07T12:00:00",
  "services": {
    "google_calendar": true,
    "twilio_sms": true,
    "email": true
  }
}
```

## 📄 License

This project is provided as-is for use with Maxi telephony integrations.

## 🆘 Support

For issues or questions:

1. Check this README thoroughly
2. Review Railway logs for error messages
3. Test each service (Calendar, Twilio, Email) independently
4. Verify all environment variables are set correctly

## 🎯 Roadmap

Potential future enhancements:

- [ ] Webhook signature verification
- [ ] Database integration for appointment tracking
- [ ] Support for multiple timezones
- [ ] Rescheduling/cancellation endpoints
- [ ] WhatsApp integration
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Custom SMS/email templates

---

**Version**: 1.0.0  
**Last Updated**: December 7, 2025  
**Maintained by**: Maxi Team
