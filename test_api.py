#!/usr/bin/env python3
"""
Test script for API endpoints.

This script tests all our lead management endpoints.
Run it to verify everything is working!
"""

import requests
import json
from typing import Dict, Any

# Base URL for our API
BASE_URL = "http://localhost:8000"


def print_response(response: requests.Response, title: str):
    """
    Pretty print an API response.
    
    Args:
        response: The HTTP response
        title: What we're testing
    """
    print(f"\n{'='*60}")
    print(f"TEST: {title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    
    try:
        # Try to parse as JSON
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        # If not JSON, print as text
        print(f"Response: {response.text}")


def test_health_endpoints():
    """Test the health check endpoints."""
    
    # Test basic health
    response = requests.get(f"{BASE_URL}/health/healthz")
    print_response(response, "Health Check")
    
    # Test readiness
    response = requests.get(f"{BASE_URL}/health/readyz")
    print_response(response, "Readiness Check")


def test_create_lead() -> int:
    """
    Test creating a new lead.
    
    Returns:
        int: The created lead's ID
    """
    
    # Sample lead data
    lead_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "postcode": "SW1A 1AA",
        "budget": 2000,
        "moveInDate": "2024-02-01",
        "occupation": "Software Engineer",
        "yearlyWage": 75000
    }
    
    response = requests.post(
        f"{BASE_URL}/api/leads/",
        json=lead_data
    )
    print_response(response, "Create Lead")
    
    if response.status_code == 201:
        return response.json()["id"]
    return None


def test_get_lead(lead_id: int):
    """
    Test getting a lead by ID.
    
    Args:
        lead_id: The lead's database ID
    """
    response = requests.get(f"{BASE_URL}/api/leads/{lead_id}")
    print_response(response, f"Get Lead {lead_id}")


def test_check_phase(lead_id: int):
    """
    Test checking lead's phase status.
    
    Args:
        lead_id: The lead's database ID
    """
    response = requests.get(f"{BASE_URL}/api/leads/{lead_id}/phase")
    print_response(response, f"Check Phase for Lead {lead_id}")


def test_store_transcript(lead_id: int):
    """
    Test storing a call transcript.
    
    Args:
        lead_id: The lead's database ID
    """
    
    # Sample transcript
    transcript_data = {
        "leadId": str(lead_id),
        "transcript": """
        Agent: Hello, this is regarding your property inquiry. Am I speaking with John Doe?
        Lead: Yes, that's me.
        Agent: Great! I see you're looking for a place in London with a budget of £2000 per month.
        Lead: That's correct.
        Agent: And you mentioned you're a Software Engineer with an annual salary of £75,000?
        Lead: Yes, that's right.
        Agent: Perfect. I can confirm all your details. Would you like to schedule a viewing?
        Lead: Yes, please.
        Agent: How about this Saturday at 2 PM?
        Lead: That works for me.
        Agent: Excellent! I'll send you the confirmation shortly.
        """
    }
    
    response = requests.post(
        f"{BASE_URL}/api/leads/{lead_id}/transcript",
        json=transcript_data
    )
    print_response(response, f"Store Transcript for Lead {lead_id}")


def test_404_error():
    """Test 404 error handling."""
    
    # Try to get non-existent lead
    response = requests.get(f"{BASE_URL}/api/leads/999999")
    print_response(response, "404 Error Test")


def main():
    """
    Run all tests in sequence.
    """
    print("\n" + "="*60)
    print("STARTING API TESTS")
    print("="*60)
    
    # Test health endpoints
    print("\n>>> Testing Health Endpoints...")
    test_health_endpoints()
    
    # Create a lead
    print("\n>>> Creating a new lead...")
    lead_id = test_create_lead()
    
    if lead_id:
        print(f"\n✅ Lead created with ID: {lead_id}")
        
        # Get the lead
        print("\n>>> Getting the lead...")
        test_get_lead(lead_id)
        
        # Check phase status
        print("\n>>> Checking phase status...")
        test_check_phase(lead_id)
        
        # Store transcript
        print("\n>>> Storing call transcript...")
        test_store_transcript(lead_id)
        
        # Check phase again (might have changed)
        print("\n>>> Checking phase after transcript...")
        test_check_phase(lead_id)
        
        # Get lead again to see transcript
        print("\n>>> Getting lead with transcript...")
        test_get_lead(lead_id)
    else:
        print("\n❌ Failed to create lead")
    
    # Test error handling
    print("\n>>> Testing error handling...")
    test_404_error()
    
    print("\n" + "="*60)
    print("API TESTS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()