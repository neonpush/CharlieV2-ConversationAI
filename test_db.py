"""
Test script to verify database and schemas work correctly.

This creates a test lead and viewing to ensure everything is connected.
"""

import asyncio
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.db.models import Lead, PropertyViewing, LeadPhase, ContractLength
from app.schemas.lead import LeadCreate, LeadResponse
import json


def test_database():
    """
    Test database operations.
    
    Creates a lead, updates it, and creates a viewing.
    """
    
    # Create a database session
    db: Session = SessionLocal()
    
    try:
        print("🔍 Testing Database Operations...")
        print("-" * 50)
        
        # 1. Create a test lead
        print("\n1️⃣ Creating a test lead...")
        
        test_lead = Lead(
            name="John Doe",
            email="john@example.com",
            phone="+447700900000",
            postcode="SW1A 1AA",
            budget=2000,
            move_in_date="2024-02-01",
            occupation="Software Engineer",
            yearly_wage=50000,
            contract_length=ContractLength.TWELVE_MONTHS,
            phase=LeadPhase.NEW,
            # Confirmation flags default to False
        )
        
        db.add(test_lead)
        db.commit()
        db.refresh(test_lead)  # Get the ID
        
        print(f"✅ Lead created with ID: {test_lead.id}")
        print(f"   Name: {test_lead.name}")
        print(f"   Phase: {test_lead.phase.value}")
        
        # 2. Update the lead with confirmations
        print("\n2️⃣ Updating lead with confirmations...")
        
        test_lead.name_confirmed = True
        test_lead.budget_confirmed = True
        test_lead.move_in_date_confirmed = True
        test_lead.occupation_confirmed = True
        test_lead.yearly_wage_confirmed = True
        test_lead.phase = LeadPhase.CONFIRM_INFO
        
        db.commit()
        print("✅ Lead updated with confirmations")
        
        # 3. Create a property viewing
        print("\n3️⃣ Creating a property viewing...")
        
        test_viewing = PropertyViewing(
            lead_id=test_lead.id,
            property_address="123 Baker Street, London",
            viewing_date="2024-02-15",
            viewing_time="14:00",
            status="scheduled",
            notes="Ground floor flat, 2 bedrooms"
        )
        
        db.add(test_viewing)
        db.commit()
        db.refresh(test_viewing)
        
        print(f"✅ Viewing created with ID: {test_viewing.id}")
        print(f"   Address: {test_viewing.property_address}")
        print(f"   Date: {test_viewing.viewing_date} at {test_viewing.viewing_time}")
        
        # 4. Test the relationship
        print("\n4️⃣ Testing relationships...")
        
        # Get lead with viewings
        lead_with_viewings = db.query(Lead).filter(Lead.id == test_lead.id).first()
        print(f"✅ Lead has {len(lead_with_viewings.viewings)} viewing(s)")
        
        # Get viewing with lead
        viewing_with_lead = db.query(PropertyViewing).filter(
            PropertyViewing.id == test_viewing.id
        ).first()
        print(f"✅ Viewing belongs to: {viewing_with_lead.lead.name}")
        
        # 5. Test Pydantic schema
        print("\n5️⃣ Testing Pydantic schemas...")
        
        # Create schema from database object
        lead_response = LeadResponse.model_validate(test_lead)
        
        # Convert to JSON (with camelCase)
        lead_json = lead_response.model_dump_json(by_alias=True)
        lead_dict = json.loads(lead_json)
        
        print("✅ Lead as JSON (camelCase):")
        print(f"   yearlyWage: {lead_dict.get('yearlyWage')}")
        print(f"   moveInDate: {lead_dict.get('moveInDate')}")
        print(f"   contractLength: {lead_dict.get('contractLength')}")
        
        # 6. Clean up test data
        print("\n6️⃣ Cleaning up test data...")
        
        db.delete(test_viewing)
        db.delete(test_lead)
        db.commit()
        
        print("✅ Test data cleaned up")
        
        print("\n" + "=" * 50)
        print("🎉 All database tests passed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        print("\n📊 Database session closed")


if __name__ == "__main__":
    # Run the test
    test_database()