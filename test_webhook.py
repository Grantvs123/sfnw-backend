"""
Test script for Maxi Telephony Webhook Handler
Usage: python test_webhook.py
"""

import requests
import json
from datetime import datetime, timedelta
import sys

# Configuration
# Change these to match your setup
WEBHOOK_URL = "http://localhost:8000/webhook"  # Change to your Railway URL for production
# WEBHOOK_URL = "https://your-app.railway.app/webhook"

# Test data
def create_test_payload():
    """Create a test webhook payload with tomorrow's date"""
    tomorrow = datetime.now() + timedelta(days=1)
    appointment_time = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)
    
    return {
        "caller": "+1234567890",
        "customer_name": "Jane Smith",
        "summary": "Customer needs consultation about our services. Interested in premium package.",
        "transcript": "Hi, I'd like to schedule a call to discuss your product offerings. I'm particularly interested in the premium package and would like to understand the pricing and features better.",
        "intent": "appointment",
        "callback_time": appointment_time.isoformat() + "Z",
        "email": "jane.smith@example.com"
    }

def test_health_endpoint():
    """Test the health check endpoint"""
    print("\n" + "="*60)
    print("Testing Health Endpoint")
    print("="*60)
    
    health_url = WEBHOOK_URL.replace("/webhook", "/health")
    
    try:
        response = requests.get(health_url, timeout=10)
        print(f"✓ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✓ Response:\n{json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"✗ Error: Unexpected status code")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Error connecting to health endpoint: {str(e)}")
        return False

def test_webhook():
    """Test the webhook endpoint with sample data"""
    print("\n" + "="*60)
    print("Testing Webhook Endpoint")
    print("="*60)
    
    payload = create_test_payload()
    
    print(f"\nSending payload to: {WEBHOOK_URL}")
    print(f"\nPayload:\n{json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"\n✓ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✓ Success! Response:\n{json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"✗ Error Response:\n{response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error connecting to webhook: {str(e)}")
        return False

def test_minimal_payload():
    """Test webhook with minimal required fields"""
    print("\n" + "="*60)
    print("Testing Minimal Payload (only required fields)")
    print("="*60)
    
    tomorrow = datetime.now() + timedelta(days=1)
    appointment_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    
    minimal_payload = {
        "caller": "+1987654321",
        "callback_time": appointment_time.isoformat() + "Z"
    }
    
    print(f"\nPayload:\n{json.dumps(minimal_payload, indent=2)}")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=minimal_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"\n✓ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✓ Success! Minimal payload accepted")
            return True
        else:
            print(f"✗ Error Response:\n{response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {str(e)}")
        return False

def test_invalid_payload():
    """Test webhook with invalid payload to verify validation"""
    print("\n" + "="*60)
    print("Testing Invalid Payload (should fail validation)")
    print("="*60)
    
    invalid_payload = {
        "caller": "123",  # Too short
        "email": "not-an-email",  # Invalid email
        "callback_time": "not-a-datetime"  # Invalid datetime
    }
    
    print(f"\nPayload:\n{json.dumps(invalid_payload, indent=2)}")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=invalid_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"\n✓ Status Code: {response.status_code}")
        
        if response.status_code == 400:
            print(f"✓ Validation working correctly - rejected invalid payload")
            print(f"Error details:\n{response.text}")
            return True
        else:
            print(f"✗ Unexpected response:\n{response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MAXI TELEPHONY WEBHOOK HANDLER - TEST SUITE")
    print("="*60)
    print(f"Target URL: {WEBHOOK_URL}")
    
    results = {
        "health_check": False,
        "full_payload": False,
        "minimal_payload": False,
        "invalid_payload": False
    }
    
    # Run tests
    results["health_check"] = test_health_endpoint()
    results["full_payload"] = test_webhook()
    results["minimal_payload"] = test_minimal_payload()
    results["invalid_payload"] = test_invalid_payload()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name.replace('_', ' ').title()}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your webhook handler is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {str(e)}")
        sys.exit(1)
