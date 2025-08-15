"""
Unit tests for system prompt generation and variable building.

Tests the core logic of how we build prompts for the voice agent.
"""

from app.services.elevenlabs_service import ElevenLabsService
from app.db.models import Lead, LeadPhase


def test_general_prompt_template_structure():
    """
    Test that the general template contains expected placeholders.
    """
    service = ElevenLabsService()
    template = service.build_general_system_prompt_template()
    
    # Check key placeholders exist
    assert "{lead_phase}" in template
    assert "{phase_missing_fields}" in template
    assert "{available_viewing_slots}" in template
    assert "{property_address}" in template
    assert "{price_per_room}" in template
    assert "{lead_name}" in template
    assert "{lead_budget}" in template
    assert "{viewing_date}" in template
    assert "{viewing_time}" in template
    
    # Check key instructions exist
    assert "Charlie from Lobby, a real estate agent" in template
    assert "VIEWING HOURS" in template
    assert "9:00 AM and 5:00 PM" in template
    assert "Monday" in template or "weekdays" in template


def test_template_variables_for_minimal_lead():
    """
    Test variable building for a lead with minimal data starting in CONFIRM_INFO.
    """
    service = ElevenLabsService()
    
    # Create a minimal lead (starts in CONFIRM_INFO by default)
    lead = Lead(
        id=1,
        phase=LeadPhase.CONFIRM_INFO,
        name="John",
        phone="+1234567890"
    )
    
    variables = service.build_template_variables(lead)
    
    # Check basic fields
    assert variables["lead_phase"] == "CONFIRM_INFO"
    assert variables["lead_name"] == "John"
    assert variables["lead_phone"] == "+1234567890"
    assert variables["lead_name_fallback"] == "John"
    
    # Check empty fields render as empty strings
    assert variables["lead_budget"] == ""
    assert variables["lead_occupation"] == ""
    assert variables["viewing_date"] == ""
    assert variables["viewing_time"] == ""
    
    # Check computed fields
    assert variables["phase_missing_fields"] != ""  # Should list missing fields
    assert "name" in variables["phase_missing_fields"]
    assert "budget" in variables["phase_missing_fields"]
    assert "move-in date" in variables["phase_missing_fields"]


def test_template_variables_for_confirm_phase():
    """
    Test variable building for a lead in CONFIRM_INFO phase.
    """
    service = ElevenLabsService()
    
    # Create a lead with data that needs confirmation
    lead = Lead(
        id=2,
        phase=LeadPhase.CONFIRM_INFO,
        name="Jane",
        name_confirmed=False,  # Needs confirmation
        budget=2000,
        budget_confirmed=True,  # Already confirmed
        move_in_date="2024-03-01",
        move_in_date_confirmed=False,  # Needs confirmation
        occupation="Engineer",
        occupation_confirmed=False,
        yearly_wage=75000,
        yearly_wage_confirmed=False
    )
    
    variables = service.build_template_variables(lead)
    
    assert variables["lead_phase"] == "CONFIRM_INFO"
    assert variables["lead_name"] == "Jane"
    assert variables["lead_budget"] == "2000"
    
    # Check unconfirmed fields are listed
    missing = variables["phase_missing_fields"]
    assert "name" in missing  # Name exists but not confirmed
    assert "budget" not in missing  # Budget is confirmed
    assert "move-in date" in missing
    assert "occupation" in missing
    assert "annual income" in missing


def test_template_variables_with_viewing():
    """
    Test variable building when viewing is scheduled.
    """
    service = ElevenLabsService()
    
    lead = Lead(
        id=3,
        phase=LeadPhase.VIEWING_BOOKED,
        name="Bob",
        viewing_date="2024-02-15",
        viewing_time="14:00",
        property_address="123 Main St, London"
    )
    
    variables = service.build_template_variables(lead)
    
    assert variables["lead_phase"] == "VIEWING_BOOKED"
    assert variables["viewing_date"] == "2024-02-15"
    assert variables["viewing_time"] == "14:00"
    assert variables["property_address"] == "123 Main St, London"


def test_price_per_room_calculation():
    """
    Test that price per room is calculated when property data exists.
    
    Note: property_bedrooms and property_monthly_cost are not on Lead model
    by default, so this will return empty unless those fields are added.
    """
    service = ElevenLabsService()
    
    # Mock a lead with property fields (if they existed)
    lead = Lead(id=4, phase=LeadPhase.CONFIRM_INFO)
    # Since these fields don't exist on Lead, price_per_room should be empty
    
    variables = service.build_template_variables(lead)
    assert variables["price_per_room"] == ""
    
    # If we added property fields to Lead:
    # lead.property_bedrooms = 3
    # lead.property_monthly_cost = 3000
    # variables = service.build_template_variables(lead)
    # assert variables["price_per_room"] == "1000"


def test_render_prompt_with_missing_variables():
    """
    Test that missing variables render as empty strings, not {placeholder}.
    """
    service = ElevenLabsService()
    
    template = "Hello {lead_name}, your budget is {lead_budget} and {unknown_field}."
    variables = {
        "lead_name": "Alice",
        # lead_budget is missing
        # unknown_field is missing
    }
    
    rendered = service.render_prompt_template(template, variables)
    
    assert rendered == "Hello Alice, your budget is  and ."
    assert "{lead_budget}" not in rendered  # No raw placeholders
    assert "{unknown_field}" not in rendered


def test_full_system_prompt_generation():
    """
    Test the complete system prompt generation flow.
    """
    service = ElevenLabsService()
    
    lead = Lead(
        id=5,
        phase=LeadPhase.CONFIRM_INFO,
        name="Charlie",
        budget=1500,
        budget_confirmed=True,
        move_in_date="March 1st",
        move_in_date_confirmed=False
    )
    
    prompt = service.build_system_prompt(lead)
    
    # Check that placeholders are replaced
    assert "{lead_name}" not in prompt
    assert "{lead_phase}" not in prompt
    
    # Check that actual values are present
    assert "Charlie" in prompt
    assert "CONFIRM_INFO" in prompt
    assert "1500" in prompt
    
    # Check that instructions are preserved
    assert "Charlie from Lobby, a real estate agent" in prompt  # Role
    assert "VIEWING HOURS" in prompt


def test_dynamic_variables_include_system_prompt():
    """
    Test that build_dynamic_variables includes the full system prompt.
    """
    service = ElevenLabsService()
    
    lead = Lead(
        id=6,
        phase=LeadPhase.CONFIRM_INFO,
        name="David",
        email="david@example.com",
        phone="+447700900000",
        budget=2500
    )
    
    variables = service.build_dynamic_variables(lead)
    
    # Check basic variables
    assert variables["lead_id"] == "6"
    assert variables["customer_name"] == "David"
    assert variables["customer_email"] == "david@example.com"
    assert variables["customer_phone"] == "+447700900000"
    assert variables["budget"] == "2500"
    assert variables["current_phase"] == "CONFIRM_INFO"
    
    # Check that unnecessary confirmation variables are NOT included
    assert "needs_name_confirm" not in variables
    assert "needs_budget_confirm" not in variables
    assert "needs_move_date_confirm" not in variables
    assert "needs_occupation_confirm" not in variables
    assert "needs_wage_confirm" not in variables
    assert "has_viewing" not in variables
    
    # Check that system_prompt is included and rendered
    assert "system_prompt" in variables
    system_prompt = variables["system_prompt"]
    assert "Charlie from Lobby, a real estate agent" in system_prompt
    assert "David" in system_prompt  # Name should be in the prompt
    assert "{lead_name}" not in system_prompt  # Should be replaced
    
    # Check that first_message is included
    assert "first_message" in variables
    assert "David" in variables["first_message"] or "there" in variables["first_message"]


def test_first_message_by_phase():
    """
    Test that first message varies by phase.
    """
    service = ElevenLabsService()
    
    # CONFIRM_INFO phase (default starting phase)
    lead = Lead(id=7, phase=LeadPhase.CONFIRM_INFO, name="Eve")
    msg = service.get_phase_first_message(lead)
    assert "Eve" in msg
    assert "Charlie calling from Lobby" in msg
    assert "property you enquired about" in msg
    assert "book your viewing" in msg
    
    # BOOKING_VIEWING phase
    lead.phase = LeadPhase.BOOKING_VIEWING
    msg = service.get_phase_first_message(lead)
    assert "Eve" in msg
    assert "viewing" in msg.lower()
    
    # VIEWING_BOOKED phase
    lead.phase = LeadPhase.VIEWING_BOOKED
    lead.viewing_date = "Saturday"
    msg = service.get_phase_first_message(lead)
    assert "Eve" in msg
    assert "confirm" in msg.lower()
    
    # No name fallback
    lead.name = None
    msg = service.get_phase_first_message(lead)
    assert "there" in msg
