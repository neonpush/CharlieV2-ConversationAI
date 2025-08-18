"""
Test script for the simple transcript analyzer.

Run this to test the analyzer with sample transcripts.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.simple_analyzer import analyzer
import json

# Sample transcript for testing
SAMPLE_TRANSCRIPT = """
Charlie: Hi, is this John Smith?

Customer: Yes, that's me.

Charlie: Great! I'm Charlie calling from Lobby about the property you enquired about. I need to confirm a few details before we can book your viewing. Do you have a moment?

Customer: Sure, go ahead.

Charlie: Perfect! First, can I confirm your budget is around £1,500 per month?

Customer: Actually, I can go up to £1,800 per month.

Charlie: That's noted, £1,800 per month. And you mentioned you're looking to move in early February?

Customer: Yes, February 1st would be ideal.

Charlie: Excellent. Can I ask what you do for work?

Customer: I'm a software engineer at a tech company.

Charlie: Great! And what's your annual income?

Customer: It's about £65,000 per year.

Charlie: Perfect. And are you looking for a 6-month or 12-month contract?

Customer: I'd prefer a 12-month contract.

Charlie: Wonderful! All your details are confirmed. Now, when would you like to view the property? We have slots available this week.

Customer: How about Thursday at 2 PM?

Charlie: Thursday at 2 PM works perfectly! I'll send you a confirmation with the property address.

Customer: Sounds good, thank you!

Charlie: You're welcome! See you Thursday at 2 PM. Have a great day!
"""

def test_analyzer():
    """Test the analyzer with a sample transcript."""
    
    print("=" * 50)
    print("Testing Simple Transcript Analyzer")
    print("=" * 50)
    
    # Check if OpenAI is configured
    if not analyzer.client:
        print("\n❌ OpenAI API key not configured!")
        print("Please set OPENAI_API_KEY in your .env file")
        return
    
    print("\n📝 Analyzing sample transcript...")
    print("-" * 30)
    
    # Create a comprehensive lead context
    # This simulates what you'd get from a real Lead object
    lead_context = {
        # Basic info
        "name": "John Smith",
        "email": "john.smith@email.com",
        "phone": "+447123456789",
        
        # Preferences
        "budget": 1500,
        "move_in_date": "February 1st",
        "postcode": "SW1A 1AA",
        
        # Employment
        "occupation": None,  # Not yet provided
        "yearly_wage": None,  # Not yet provided
        "contract_length": None,  # Not yet provided
        
        # Property details
        "property_address": "123 High Street, London SW1A 1AA",
        "property_cost": 1800,
        "bedroom_count": 2,
        
        # Current status
        "phase": "CONFIRM_INFO",
        
        # Confirmation flags (nothing confirmed yet)
        "name_confirmed": False,
        "budget_confirmed": False,
        "move_in_date_confirmed": False,
        "occupation_confirmed": False,
        "yearly_wage_confirmed": False,
        "contract_length_confirmed": False,
        
        # No viewing scheduled yet
        "viewing_date": None,
        "viewing_time": None,
    }
    
    # Analyze the transcript with full context
    result = analyzer.analyze_transcript(
        SAMPLE_TRANSCRIPT,
        lead_context=lead_context
    )
    
    # Display results
    print("\n📊 Analysis Results:")
    print("-" * 30)
    print(json.dumps(result, indent=2))
    
    # Extract database updates
    print("\n💾 Database Updates to Apply:")
    print("-" * 30)
    updates = analyzer.extract_updates_for_lead(result)
    for field, value in updates.items():
        print(f"  {field}: {value}")
    
    # Check if viewing was booked
    if result.get("viewing", {}).get("booked"):
        print("\n✅ Viewing successfully booked!")
        print(f"  Date: {result['viewing'].get('date')}")
        print(f"  Time: {result['viewing'].get('time')}")
    
    # Display call outcome
    outcome = result.get("call_outcome", {})
    if outcome.get("successful"):
        print("\n✅ Call was successful!")
    else:
        print(f"\n❌ Call issue: {outcome.get('reason')}")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_analyzer()
