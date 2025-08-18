"""
Test script for availability extraction in transcript analyzer.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.simple_analyzer import analyzer
import json

# Sample transcript with availability collection
AVAILABILITY_TRANSCRIPT = """
Charlie: Hello Sarah! I'm calling to schedule your property viewing. Can you tell me when you're generally available this week?

Customer: Hi Charlie! Yes, I'm pretty flexible. Let me think...

Charlie: Take your time. I need to check with the landlord anyway, so multiple options would be great.

Customer: Okay, so I'm available Monday after 3 PM, Wednesday morning before 11, and Friday anytime in the afternoon.

Charlie: Perfect! So that's Monday after 3 PM, Wednesday morning before 11 AM, and Friday afternoon. Any particular preference?

Customer: Monday after 3 would be ideal, but Wednesday morning works too if that's better for the landlord.

Charlie: Great! I'll check with the landlord about these times and get back to you tomorrow. Should I call you on this number?

Customer: Yes, this number is perfect. Thanks Charlie!

Charlie: You're welcome Sarah! I'll be in touch soon with confirmation.
"""



def test_availability_extraction():
    """Test availability extraction from transcripts."""
    
    print("=" * 60)
    print("Testing Availability Extraction")
    print("=" * 60)
    
    # Check if OpenAI is configured
    if not analyzer.client:
        print("\n❌ OpenAI API key not configured!")
        print("Please set OPENAI_API_KEY in your .env file")
        return
    
    print("\n📞 Testing Availability Collection")
    print("-" * 30)
    
    lead_context = {
        "name": "Sarah Johnson",
        "phase": "BOOKING_VIEWING",
        "name_confirmed": True,
        "budget_confirmed": True,
        "move_in_date_confirmed": True,
        "occupation_confirmed": True,
        "yearly_wage_confirmed": True,
        "contract_length_confirmed": True,
        "availability_slots": None,  # No availability yet
        "availability_confirmed": False,
        "landlord_approval_pending": False,
        "viewing_date": None,
        "viewing_time": None,
    }
    
    print("📝 Analyzing availability collection transcript...")
    result = analyzer.analyze_transcript(AVAILABILITY_TRANSCRIPT, lead_context)
    
    print("\n📊 Availability Analysis:")
    availability = result.get("availability", {})
    print(f"  Slots provided: {availability.get('slots_provided')}")
    print(f"  Confirmed: {availability.get('confirmed')}")
    print(f"  Landlord approval needed: {availability.get('landlord_approval_needed')}")
    print(f"  Confidence: {availability.get('confidence')}")
    
    if availability.get('slots'):
        print(f"  📅 Extracted {len(availability['slots'])} availability slots:")
        for i, slot in enumerate(availability['slots'], 1):
            print(f"    {i}. {slot.get('date')} at {slot.get('time')} ({slot.get('notes', 'no notes')})")
    
    # Extract database updates
    updates = analyzer.extract_updates_for_lead(result)
    print(f"\n💾 Database Updates:")
    for field, value in updates.items():
        print(f"  {field}: {value}")
    
    # Show call outcome
    call_outcome = result.get("call_outcome", {})
    print(f"\n📞 Call Outcome:")
    print(f"  Successful: {call_outcome.get('successful')}")
    print(f"  Reason: {call_outcome.get('reason')}")
    print(f"  Follow-up needed: {call_outcome.get('follow_up_needed')}")
    
    print("\n✅ Availability collection tested successfully!")
    print("\n🔄 Workflow After This Call:")
    print("1. ✅ Lead availability slots stored in database")
    print("2. ✅ landlord_approval_pending = True")
    print("3. 👤 YOU manually contact landlord with these slots")
    print("4. 👤 YOU get landlord's preferred time")
    print("5. 👤 YOU manually book final viewing (or make another call)")
    print("6. 🎯 Phase progresses to VIEWING_BOOKED when viewing_date/time set")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_availability_extraction()
