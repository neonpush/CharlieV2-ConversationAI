#!/usr/bin/env python3
"""
Script to show example system prompts for different lead scenarios.

Run this to see what the final system prompt looks like!
"""

from app.services.elevenlabs_service import ElevenLabsService
from app.db.models import Lead, LeadPhase


def print_separator(title: str):
    """Print a nice separator for readability."""
    print("\n" + "="*80)
    print(f" {title} ")
    print("="*80 + "\n")


def show_minimal_lead_prompt():
    """Show prompt for a lead with minimal data starting in CONFIRM_INFO."""
    print_separator("SCENARIO 1: MINIMAL LEAD (Starting in CONFIRM_INFO)")
    
    lead = Lead(
        id=1,
        phase=LeadPhase.CONFIRM_INFO,
        name="Sarah",
        phone="+447700900123"
    )
    
    service = ElevenLabsService()
    prompt = service.build_system_prompt(lead)
    first_message = service.get_phase_first_message(lead)
    
    print("LEAD DATA:")
    print(f"  - Name: {lead.name}")
    print(f"  - Phone: {lead.phone}")
    print(f"  - Phase: {lead.phase.value}")
    print(f"  - Has budget: No")
    print(f"  - Has move date: No")
    
    print("\nFIRST MESSAGE:")
    print(f'  "{first_message}"')
    
    print("\nSYSTEM PROMPT:")
    print("-" * 40)
    print(prompt)


def show_confirm_info_prompt():
    """Show prompt for a lead needing confirmation."""
    print_separator("SCENARIO 2: CONFIRM_INFO (Has data, needs confirmation)")
    
    lead = Lead(
        id=2,
        phase=LeadPhase.CONFIRM_INFO,
        name="James",
        name_confirmed=False,  # Needs confirmation
        phone="+447700900456",
        email="james@example.com",
        budget=2500,
        budget_confirmed=True,  # Already confirmed
        move_in_date="March 1st",
        move_in_date_confirmed=False,  # Needs confirmation
        occupation="Software Engineer",
        occupation_confirmed=False,  # Needs confirmation
        yearly_wage=85000,
        yearly_wage_confirmed=False,  # Needs confirmation
        postcode="SW1A 1AA"
    )
    
    service = ElevenLabsService()
    prompt = service.build_system_prompt(lead)
    first_message = service.get_phase_first_message(lead)
    
    print("LEAD DATA:")
    print(f"  - Name: {lead.name} (confirmed: {lead.name_confirmed})")
    print(f"  - Budget: £{lead.budget} (confirmed: {lead.budget_confirmed})")
    print(f"  - Move date: {lead.move_in_date} (confirmed: {lead.move_in_date_confirmed})")
    print(f"  - Occupation: {lead.occupation} (confirmed: {lead.occupation_confirmed})")
    print(f"  - Yearly wage: £{lead.yearly_wage} (confirmed: {lead.yearly_wage_confirmed})")
    print(f"  - Phase: {lead.phase.value}")
    
    print("\nFIRST MESSAGE:")
    print(f'  "{first_message}"')
    
    print("\nSYSTEM PROMPT:")
    print("-" * 40)
    print(prompt)


def show_viewing_booked_prompt():
    """Show prompt for a lead with viewing scheduled."""
    print_separator("SCENARIO 3: VIEWING_BOOKED (Has appointment)")
    
    lead = Lead(
        id=3,
        phase=LeadPhase.VIEWING_BOOKED,
        name="Emma",
        name_confirmed=True,
        phone="+447700900789",
        email="emma@example.com",
        budget=3000,
        budget_confirmed=True,
        move_in_date="February 15th",
        move_in_date_confirmed=True,
        occupation="Marketing Manager",
        occupation_confirmed=True,
        yearly_wage=65000,
        yearly_wage_confirmed=True,
        viewing_date="Saturday, February 10th",
        viewing_time="2:00 PM",
        property_address="123 Baker Street, London, NW1 6XE"
    )
    
    service = ElevenLabsService()
    prompt = service.build_system_prompt(lead)
    first_message = service.get_phase_first_message(lead)
    
    print("LEAD DATA:")
    print(f"  - Name: {lead.name} (confirmed: {lead.name_confirmed})")
    print(f"  - Budget: £{lead.budget} (confirmed: {lead.budget_confirmed})")
    print(f"  - Move date: {lead.move_in_date} (confirmed: {lead.move_in_date_confirmed})")
    print(f"  - Occupation: {lead.occupation} (confirmed: {lead.occupation_confirmed})")
    print(f"  - Yearly wage: £{lead.yearly_wage} (confirmed: {lead.yearly_wage_confirmed})")
    print(f"  - Phase: {lead.phase.value}")
    print(f"  - Viewing: {lead.viewing_date} at {lead.viewing_time}")
    print(f"  - Property: {lead.property_address}")
    
    print("\nFIRST MESSAGE:")
    print(f'  "{first_message}"')
    
    print("\nSYSTEM PROMPT:")
    print("-" * 40)
    print(prompt)


def show_dynamic_variables():
    """Show the full dynamic variables including system prompt."""
    print_separator("BONUS: Full Dynamic Variables (What gets sent to ElevenLabs)")
    
    lead = Lead(
        id=4,
        phase=LeadPhase.BOOKING_VIEWING,
        name="Oliver",
        name_confirmed=True,
        phone="+447700900321",
        email="oliver@example.com",
        budget=2000,
        budget_confirmed=True,
        move_in_date="March 15th",
        move_in_date_confirmed=True,
        occupation="Teacher",
        occupation_confirmed=True,
        yearly_wage=45000,
        yearly_wage_confirmed=True
    )
    
    service = ElevenLabsService()
    variables = service.build_dynamic_variables(lead)
    
    print("LEAD PHASE: BOOKING_VIEWING (Ready to schedule viewing)")
    print("\nDYNAMIC VARIABLES SENT TO ELEVENLABS:")
    print("-" * 40)
    
    # Print each variable except system_prompt (too long)
    for key, value in variables.items():
        if key == "system_prompt":
            print(f"  {key}: [Full prompt - {len(value)} characters]")
        elif key == "first_message":
            print(f"  {key}: \"{value}\"")
        else:
            print(f"  {key}: {value}")
    
    print("\nSYSTEM PROMPT CONTENT:")
    print("-" * 40)
    print(variables["system_prompt"])


def main():
    """Run all examples."""
    print("\n" + "🤖"*40)
    print(" SYSTEM PROMPT EXAMPLES FOR DIFFERENT LEAD SCENARIOS")
    print("🤖"*40)
    
    show_minimal_lead_prompt()
    show_confirm_info_prompt()
    show_viewing_booked_prompt()
    show_dynamic_variables()
    
    print("\n" + "="*80)
    print(" END OF EXAMPLES")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
