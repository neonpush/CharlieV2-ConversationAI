#!/usr/bin/env python3
"""
Script to test the full pipeline:
1. Create a lead via API
2. Initiate a call to that lead
3. Check call status

Usage: python scripts/test_pipeline.py
"""

import requests
import json
import time
import sys
import os
from datetime import datetime

# Configuration - update these based on your setup
BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "wsec_1ed267b51eaf39a2f218698a8d98c372b13692c1dc7af2dd94c457acad40197b")

# Test phone number - update this to your test number
TEST_PHONE = "+447599434463"  # From your env.example

def create_lead():
    """
    Step 1: Create a lead via the API
    """
    print("\n📝 Creating lead...")
    
    lead_data = {
        "name": "Test User",
        "phone": TEST_PHONE,
        "email": "test@example.com",
        "postcode": "SW1A 1AA",
        "budget": 2500,
        "moveInDate": "2025-02-01",
        "occupation": "Software Engineer",
        "yearlyWage": 65000,
        "contractLength": "TWELVE_MONTHS",
        "propertyAddress": "123 Test Street, London"
    }
    
    headers = {
        "X-Webhook-Secret": WEBHOOK_SECRET,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/leads/",
            json=lead_data,
            headers=headers
        )
        
        if response.status_code == 201:
            lead = response.json()
            print(f"✅ Lead created successfully!")
            print(f"   ID: {lead['id']}")
            print(f"   Name: {lead['name']}")
            print(f"   Phone: {lead['phone']}")
            print(f"   Phase: {lead['phase']}")
            return lead
        else:
            print(f"❌ Failed to create lead: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating lead: {e}")
        return None


def initiate_call(lead_id):
    """
    Step 2: Initiate a call to the lead
    """
    print(f"\n📞 Initiating call to lead {lead_id}...")
    
    call_data = {
        "lead_id": lead_id
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/calls/initiate",
            json=call_data
        )
        
        if response.status_code == 200:
            call_info = response.json()
            print(f"✅ Call initiated successfully!")
            print(f"   Call SID: {call_info.get('call_sid')}")
            print(f"   Status: {call_info.get('status')}")
            print(f"   To: {call_info.get('phone')}")
            
            # Show some dynamic variables that were built
            if 'dynamic_variables' in call_info:
                vars = call_info['dynamic_variables']
                print(f"\n📊 Dynamic Variables Built:")
                print(f"   Lead Phase: {vars.get('lead_phase')}")
                print(f"   Lead Name: {vars.get('lead_name')}")
                print(f"   Has All Info: {vars.get('has_all_required_info')}")
                
            return call_info
        else:
            print(f"❌ Failed to initiate call: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error initiating call: {e}")
        return None


def check_call_status(call_sid):
    """
    Step 3: Check the status of the call
    """
    print(f"\n📊 Checking call status for {call_sid}...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/calls/status/{call_sid}"
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"✅ Call Status:")
            print(f"   Status: {status.get('status')}")
            print(f"   Duration: {status.get('duration')} seconds")
            print(f"   Direction: {status.get('direction')}")
            return status
        else:
            print(f"⚠️  Could not get call status: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return None


def test_twiml_endpoint(lead_id):
    """
    Optional: Test the TwiML endpoint directly
    """
    print(f"\n🔧 Testing TwiML endpoint for lead {lead_id}...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/twiml/answer?lead_id={lead_id}"
        )
        
        if response.status_code == 200:
            print(f"✅ TwiML endpoint responded successfully")
            print(f"   Content-Type: {response.headers.get('content-type')}")
            
            # Show first 500 chars of TwiML
            twiml = response.text[:500]
            print(f"   TwiML Preview: {twiml}...")
            return True
        else:
            print(f"❌ TwiML endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing TwiML: {e}")
        return False


def main():
    """
    Main test flow
    """
    print("=" * 60)
    print("🚀 LEAD MANAGEMENT PIPELINE TEST")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Phone: {TEST_PHONE}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Step 1: Create lead
    lead = create_lead()
    if not lead:
        print("\n❌ Pipeline test failed at lead creation")
        sys.exit(1)
    
    # Step 2: Test TwiML endpoint (optional)
    test_twiml_endpoint(lead['id'])
    
    # Step 3: Initiate call
    call_info = initiate_call(lead['id'])
    if not call_info:
        print("\n⚠️  Call initiation failed - this might be due to:")
        print("   - Invalid Twilio credentials")
        print("   - No ElevenLabs agent URL configured")
        print("   - Twilio account restrictions")
        # Continue anyway to show what would happen
    
    # Step 4: Check call status (if we have a call SID)
    if call_info and call_info.get('call_sid'):
        time.sleep(2)  # Wait a bit for call to process
        check_call_status(call_info['call_sid'])
    
    print("\n" + "=" * 60)
    print("✅ Pipeline test completed!")
    print("=" * 60)
    
    print("\n📝 Next steps:")
    print("1. Check your Twilio dashboard for call logs")
    print("2. If using ElevenLabs, check the agent dashboard")
    print("3. Monitor server logs for any errors")
    print("4. The call should connect to the phone number provided")


if __name__ == "__main__":
    # Allow overriding via command line
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        print(f"Using custom base URL: {BASE_URL}")
    
    main()
