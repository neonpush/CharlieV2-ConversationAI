"""
Simple transcript analyzer using OpenAI.

This service analyzes call transcripts and extracts:
- Confirmed information (name, budget, move-in date, etc.)
- Viewing booking details
- Phase progression signals
"""

import json
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from openai import OpenAI
from app.core.config import settings

# Avoid circular imports
if TYPE_CHECKING:
    from app.db.models import Lead

logger = logging.getLogger(__name__)


class SimpleTranscriptAnalyzer:
    """
    Simple analyzer that uses OpenAI to extract information from transcripts.
    
    We start simple:
    1. Send transcript to OpenAI
    2. Get structured data back
    3. Return extracted information
    """
    
    def __init__(self):
        """Initialize the analyzer with OpenAI client."""
        if settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)
        else:
            self.client = None
            logger.warning("OpenAI API key not configured - analyzer disabled")
    
    @staticmethod
    def lead_to_context(lead: "Lead") -> Dict[str, Any]:
        """
        Convert a Lead object to a context dictionary for the analyzer.
        
        Args:
            lead: The Lead database object
            
        Returns:
            Dictionary with all lead information for context
        """
        context = {
            # Basic info
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            
            # Preferences
            "budget": lead.budget,
            "move_in_date": lead.move_in_date,
            "postcode": lead.postcode,
            
            # Employment
            "occupation": lead.occupation,
            "yearly_wage": lead.yearly_wage,
            "contract_length": lead.contract_length.value if lead.contract_length else None,
            
            # Property details
            "property_address": lead.property_address,
            "property_cost": lead.property_cost,
            "bedroom_count": lead.bedroom_count,
            "bathroom_count": lead.bathroom_count,
            "address_line_1": lead.address_line_1,
            "availability_at": lead.availability_at,
            "deposit_cost": lead.deposit_cost,
            "is_bills_included": lead.is_bills_included,
            
            # Current status
            "phase": lead.phase.value if lead.phase else "CONFIRM_INFO",
            
            # Confirmation flags
            "name_confirmed": lead.name_confirmed,
            "budget_confirmed": lead.budget_confirmed,
            "move_in_date_confirmed": lead.move_in_date_confirmed,
            "occupation_confirmed": lead.occupation_confirmed,
            "yearly_wage_confirmed": lead.yearly_wage_confirmed,
            "contract_length_confirmed": lead.contract_length_confirmed,
            
            # Viewing info
            "viewing_date": lead.viewing_date,
            "viewing_time": lead.viewing_time,
            "viewing_notes": lead.viewing_notes,
            
            # Availability info
            "availability_slots": lead.availability_slots,
            "availability_notes": lead.availability_notes,
            "availability_confirmed": lead.availability_confirmed,
            "landlord_approval_pending": lead.landlord_approval_pending,
        }
        
        return context
    
    def analyze_transcript(
        self, 
        transcript: str,
        lead_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a transcript and extract relevant information.
        
        Args:
            transcript: The conversation transcript
            lead_context: Optional context about the lead (current phase, existing data)
            
        Returns:
            Dictionary with extracted information and confidence scores
        """
        
        if not self.client:
            logger.warning("OpenAI client not initialized - skipping analysis")
            return {"error": "OpenAI not configured"}
        
        # Build the system prompt
        system_prompt = """You are analyzing a phone call transcript between Charlie (a property rental agent) and a potential tenant.
        
Extract the following information:
1. What information was confirmed (name, budget, move-in date, occupation, yearly income, contract length)
2. Lead availability for viewings (multiple time slots they mentioned)
3. Whether a specific viewing was booked (final confirmed date and time)
4. Any concerns or objections raised
5. Overall success of the call

Return JSON with this structure:
{
    "confirmations": {
        "name": {"confirmed": true/false, "value": "actual name if mentioned", "confidence": 0.0-1.0},
        "budget": {"confirmed": true/false, "value": number or null, "confidence": 0.0-1.0},
        "move_in_date": {"confirmed": true/false, "value": "date string or null", "confidence": 0.0-1.0},
        "occupation": {"confirmed": true/false, "value": "occupation or null", "confidence": 0.0-1.0},
        "yearly_wage": {"confirmed": true/false, "value": number or null, "confidence": 0.0-1.0},
        "contract_length": {"confirmed": true/false, "value": "6_months/12_months/etc or null", "confidence": 0.0-1.0}
    },
    "availability": {
        "slots_provided": true/false,
        "slots": [
            {"date": "Monday", "time": "2 PM", "notes": "preferred"},
            {"date": "Wednesday", "time": "morning", "notes": "flexible"}
        ],
        "confirmed": true/false,
        "landlord_approval_needed": true/false,
        "confidence": 0.0-1.0
    },
    "viewing": {
        "booked": true/false,
        "date": "date string or null",
        "time": "time string or null",
        "confidence": 0.0-1.0
    },
    "call_outcome": {
        "successful": true/false,
        "reason": "brief explanation",
        "follow_up_needed": true/false
    },
    "key_points": ["important points from the conversation"]
}"""
        
        # Build the user prompt with all lead context
        user_prompt = f"Analyze this transcript:\n\n{transcript}"
        
        if lead_context:
            context_str = f"\n\nExisting information about this lead:\n"
            
            # Basic info
            context_str += f"- Name: {lead_context.get('name', 'Not provided')}\n"
            context_str += f"- Email: {lead_context.get('email', 'Not provided')}\n"
            context_str += f"- Phone: {lead_context.get('phone', 'Not provided')}\n"
            
            # Preferences
            context_str += f"- Budget: £{lead_context.get('budget', 'Not specified')} per month\n"
            context_str += f"- Move-in date: {lead_context.get('move_in_date', 'Not specified')}\n"
            context_str += f"- Postcode: {lead_context.get('postcode', 'Not specified')}\n"
            
            # Employment
            context_str += f"- Occupation: {lead_context.get('occupation', 'Not specified')}\n"
            context_str += f"- Yearly wage: £{lead_context.get('yearly_wage', 'Not specified')}\n"
            context_str += f"- Contract length preference: {lead_context.get('contract_length', 'Not specified')}\n"
            
            # Property details
            if lead_context.get('property_address'):
                context_str += f"- Property address: {lead_context.get('property_address')}\n"
            if lead_context.get('property_cost'):
                context_str += f"- Property cost: £{lead_context.get('property_cost')} per month\n"
            if lead_context.get('bedroom_count'):
                context_str += f"- Bedrooms: {lead_context.get('bedroom_count')}\n"
            
            # Current status
            context_str += f"\n- Current phase: {lead_context.get('phase', 'CONFIRM_INFO')}\n"
            
            # Confirmation status
            context_str += f"\nConfirmation status:\n"
            context_str += f"- Name confirmed: {lead_context.get('name_confirmed', False)}\n"
            context_str += f"- Budget confirmed: {lead_context.get('budget_confirmed', False)}\n"
            context_str += f"- Move-in date confirmed: {lead_context.get('move_in_date_confirmed', False)}\n"
            context_str += f"- Occupation confirmed: {lead_context.get('occupation_confirmed', False)}\n"
            context_str += f"- Yearly wage confirmed: {lead_context.get('yearly_wage_confirmed', False)}\n"
            context_str += f"- Contract length confirmed: {lead_context.get('contract_length_confirmed', False)}\n"
            
            # Viewing info if exists
            if lead_context.get('viewing_date') or lead_context.get('viewing_time'):
                context_str += f"\nExisting viewing:\n"
                context_str += f"- Date: {lead_context.get('viewing_date', 'Not set')}\n"
                context_str += f"- Time: {lead_context.get('viewing_time', 'Not set')}\n"
            
            user_prompt += context_str
        
        try:
            import time
            start_time = time.time()
            
            # Log analysis start with context
            logger.info(f"🤖 Starting transcript analysis:")
            logger.info(f"  📝 Transcript length: {len(transcript)} chars")
            logger.info(f"  🎯 Lead phase: {lead_context.get('phase', 'Unknown') if lead_context else 'No context'}")
            logger.info(f"  🔑 Model: {settings.openai_model}")
            
            # Create the request parameters
            request_params = {
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}  # Force JSON response
            }
            
            # Only add temperature for models that support it (not GPT-5)
            if not settings.openai_model.startswith("gpt-5"):
                request_params["temperature"] = 0.1  # Low temperature for consistent extraction
                logger.debug("  🌡️ Temperature: 0.1")
            else:
                logger.debug("  🌡️ Temperature: default (GPT-5)")
            
            # Call OpenAI
            logger.info("📡 Sending request to OpenAI...")
            response = self.client.chat.completions.create(**request_params)
            
            # Calculate timing and usage
            analysis_duration = time.time() - start_time
            usage = response.usage if hasattr(response, 'usage') else None
            
            logger.info(f"✅ OpenAI response received:")
            logger.info(f"  ⏱️ Duration: {analysis_duration:.2f}s")
            if usage:
                logger.info(f"  🔢 Tokens - Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens}, Total: {usage.total_tokens}")
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Log detailed analysis results
            self._log_analysis_results(result, analysis_duration)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error analyzing transcript: {str(e)}")
            logger.error(f"  📝 Transcript preview: {transcript[:200]}...")
            return {
                "error": str(e),
                "confirmations": {},
                "viewing": {"booked": False},
                "call_outcome": {"successful": False, "reason": "Analysis failed"}
            }
    
    def _log_analysis_results(self, result: Dict[str, Any], duration: float):
        """Log detailed analysis results for monitoring and debugging."""
        
        logger.info("📊 Analysis Results Summary:")
        
        # Log call outcome
        call_outcome = result.get("call_outcome", {})
        logger.info(f"  📞 Call successful: {call_outcome.get('successful', False)}")
        logger.info(f"  📝 Reason: {call_outcome.get('reason', 'N/A')}")
        logger.info(f"  🔄 Follow-up needed: {call_outcome.get('follow_up_needed', False)}")
        
        # Log confirmations with confidence scores
        confirmations = result.get("confirmations", {})
        confirmed_count = sum(1 for conf in confirmations.values() if conf.get("confirmed"))
        logger.info(f"  ✅ Confirmations: {confirmed_count}/{len(confirmations)} fields")
        
        for field, data in confirmations.items():
            if data.get("confirmed"):
                confidence = data.get("confidence", 0)
                value = data.get("value")
                logger.info(f"    ✓ {field}: {value} (confidence: {confidence:.2f})")
        
        # Log availability information
        availability = result.get("availability", {})
        if availability.get("slots_provided"):
            slots = availability.get("slots", [])
            logger.info(f"  📅 Availability: {len(slots)} slots provided (confidence: {availability.get('confidence', 0):.2f})")
            for i, slot in enumerate(slots, 1):
                logger.info(f"    {i}. {slot.get('date')} at {slot.get('time')} - {slot.get('notes', 'no notes')}")
            logger.info(f"  🏠 Landlord approval needed: {availability.get('landlord_approval_needed', False)}")
        
        # Log viewing booking
        viewing = result.get("viewing", {})
        if viewing.get("booked"):
            logger.info(f"  👁️ Viewing booked: {viewing.get('date')} at {viewing.get('time')} (confidence: {viewing.get('confidence', 0):.2f})")
        
        # Log key conversation points
        key_points = result.get("key_points", [])
        if key_points:
            logger.info(f"  💡 Key points ({len(key_points)}):")
            for i, point in enumerate(key_points[:3], 1):  # Log first 3 points
                logger.info(f"    {i}. {point}")
    
    def extract_updates_for_lead(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert analysis result into database updates.
        
        Takes the raw analysis and determines what fields should be updated
        in the database based on confidence thresholds.
        
        Args:
            analysis_result: The result from analyze_transcript
            
        Returns:
            Dictionary of field updates to apply to the lead
        """
        
        updates = {}
        confirmations = analysis_result.get("confirmations", {})
        
        # Check each confirmation field
        for field, data in confirmations.items():
            if data.get("confirmed") and data.get("confidence", 0) >= settings.analyzer_confidence_threshold:
                # Field was confirmed with high confidence
                updates[f"{field}_confirmed"] = True
                
                # Also update the value if provided
                if data.get("value") is not None:
                    # Map contract_length values to our enum
                    if field == "contract_length":
                        value = data["value"]
                        # Simple mapping - expand as needed
                        if "6" in str(value):
                            updates[field] = "SIX_MONTHS"
                        elif "12" in str(value):
                            updates[field] = "TWELVE_MONTHS"
                        else:
                            updates[field] = value
                    else:
                        updates[field] = data["value"]
        
        # Check availability information
        availability = analysis_result.get("availability", {})
        if availability.get("slots_provided") and availability.get("confidence", 0) >= settings.analyzer_confidence_threshold:
            if availability.get("slots"):
                # Convert slots to JSON string for storage
                import json
                updates["availability_slots"] = json.dumps(availability["slots"])
            
            if availability.get("confirmed"):
                updates["availability_confirmed"] = True
                
            if availability.get("landlord_approval_needed"):
                updates["landlord_approval_pending"] = True
        
        # Check viewing booking (final specific time)
        viewing = analysis_result.get("viewing", {})
        if viewing.get("booked") and viewing.get("confidence", 0) >= settings.analyzer_confidence_threshold:
            if viewing.get("date"):
                updates["viewing_date"] = viewing["date"]
            if viewing.get("time"):
                updates["viewing_time"] = viewing["time"]
        
        # Log detailed extraction results
        logger.info(f"💾 Database Update Extraction:")
        logger.info(f"  📊 Total updates: {len(updates)}")
        logger.info(f"  🎯 Confidence threshold: {settings.analyzer_confidence_threshold}")
        
        if updates:
            logger.info("  📝 Fields to update:")
            for field, value in updates.items():
                if isinstance(value, str) and len(value) > 100:
                    # Truncate long values (like JSON)
                    display_value = value[:100] + "..."
                else:
                    display_value = value
                logger.info(f"    ✓ {field}: {display_value}")
        else:
            logger.info("  ⚠️ No updates meet confidence threshold")
            
            # Log what was below threshold for debugging
            confirmations = analysis_result.get("confirmations", {})
            low_confidence = []
            for field, data in confirmations.items():
                if data.get("confirmed") and data.get("confidence", 0) < settings.analyzer_confidence_threshold:
                    low_confidence.append(f"{field} ({data.get('confidence', 0):.2f})")
            
            if low_confidence:
                logger.info(f"  🔻 Below threshold: {', '.join(low_confidence)}")
        
        return updates


# Create a singleton instance
analyzer = SimpleTranscriptAnalyzer()
