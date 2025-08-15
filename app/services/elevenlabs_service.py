"""
ElevenLabs service for managing AI agent conversations.

This service handles:
- Building dynamic variables for conversations
- Creating custom agent URLs with context
- Managing conversation configuration
"""

from typing import Dict, Any, Optional
from app.core.config import settings
from app.db.models import Lead
import logging
import json
from urllib.parse import urlencode
import httpx
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """
    Service for building ElevenLabs conversation context.
    
    Since ElevenLabs doesn't have a pre-population API,
    we use dynamic variables and custom prompts instead.
    """
    
    def __init__(self):
        """
        Initialize ElevenLabs service configuration.
        """
        self.agent_id = settings.elevenlabs_agent_id
        self.agent_url = settings.elevenlabs_agent_url
    
    def build_dynamic_variables(self, lead: Lead) -> Dict[str, Any]:
        """
        Build dynamic variables from lead data.
        
        These variables can be used in the agent's prompts
        using {{variable_name}} syntax.
        
        Args:
            lead: The lead object
            
        Returns:
            Dict of dynamic variables
        """
        logger.info(f"Building dynamic variables for lead {lead.id}")
        
        # Build flat dynamic variables
        # ElevenLabs supports simple key-value pairs
        phase_str = lead.phase.value if hasattr(lead.phase, "value") else (lead.phase or "")

        variables = {
            # Identity
            "lead_id": str(lead.id),
            "customer_name": lead.name or "there",
            "customer_email": lead.email or "",
            "customer_phone": lead.phone or "",
            
            # Preferences
            "postcode": lead.postcode or "",
            "budget": str(lead.budget) if lead.budget else "",
            "move_in_date": lead.move_in_date or "",
            
            # Employment
            "occupation": lead.occupation or "",
            "yearly_wage": str(lead.yearly_wage) if lead.yearly_wage else "",
            "contract_length": (lead.contract_length.value if getattr(lead, "contract_length", None) else ""),
            
            # Current status
            "current_phase": phase_str,
            
            # Viewing info
            "viewing_date": lead.viewing_date or "",
            "viewing_time": lead.viewing_time or "",
        }
        
        # Remove empty values to keep it clean
        variables = {k: v for k, v in variables.items() if v}
        
        # ADD SYSTEM PROMPT AS A VARIABLE
        # Build a comprehensive general system prompt filled with lead variables
        system_prompt = self.build_system_prompt(lead)
        variables["system_prompt"] = system_prompt
        
        # Also add first message
        variables["first_message"] = self.get_phase_first_message(lead)
        
        logger.debug(f"Dynamic variables: {json.dumps(variables, indent=2)}")
        
        return variables
    
    def build_general_system_prompt_template(self) -> str:
        """
        General system prompt template for the voice agent.

        This template avoids complex conditional templating. It is rendered with
        simple variable substitution and is suitable to send as a single
        `system_prompt` string to the agent.

        Returns:
            The raw template string with placeholders like {lead_phase}.
        """
        return (
            "You are Charlie from Lobby, a real estate agent. Check {lead_phase} to understand the conversation goal.\n\n"
            "Phase-specific behavior:\n"
            "- CONFIRM_INFO: First confirm/collect {phase_missing_fields}. Once all information is confirmed, proceed to book a viewing.\n"
            "- BOOKING_VIEWING: Offer slots from {available_viewing_slots}\n"
            "- VIEWING_BOOKED: Viewing is on {viewing_date} at {viewing_time}\n\n"
            "IMPORTANT: After your initial greeting, WAIT for the person to respond before proceeding with any details or questions.\n\n"
            "NATURAL CONVERSATION RULES:\n"
            "- Mention the property address ONCE when you first bring it up, then use \"the property\" or \"it\"\n"
            "- Don't repeat information unnecessarily - be conversational\n"
            "- Keep responses brief and natural (1-2 sentences)\n"
            "- Don't over-confirm details that have already been agreed\n\n"
            "Personality:\n"
            "- Friendly and personable. You're Charlie from Lobby, a warm and enthusiastic property rental assistant\n"
            "- Genuinely helpful; show real interest in helping tenants find their perfect home\n"
            "- Natural conversationalist; speak like a real person on a phone call\n"
            "- Enthusiastic and positive\n\n"
            "Environment:\n"
            "- Phone call context with real-time back-and-forth\n"
            "- Property rental setting; focus on booking property viewings\n\n"
            "Tone:\n"
            "- Conversational and casual (e.g., \"Great!\", \"Perfect!\", \"I see\")\n"
            "- Brief and concise (1-2 sentences)\n"
            "- Warm but professional\n"
            "- Flexible and adaptive—adjust to how the caller shares information\n\n"
            "IMPORTANT: After your initial greeting and request to confirm details, WAIT for permission. If they say yes, proceed. If they're busy, offer to call back later.\n\n"
            "VIEWING HOURS: Viewings can ONLY be booked between 9:00 AM and 5:00 PM on weekdays (Monday–Friday). Do not offer or accept viewing times outside these hours.\n\n"
            "CRITICAL PROPERTY REFERENCE RULES:\n"
            "- On first mention say: \"the property at {property_address}\"\n"
            "- If it's a {property_bedrooms} property at {property_monthly_cost}/month, say: \"that's £{price_per_room} per bedroom\"\n\n"
            "Lead context (if available):\n"
            "- Name: {lead_name}\n"
            "- Phone: {lead_phone}\n"
            "- Budget: {lead_budget}\n"
            "- Move-in date: {lead_move_in_date}\n"
            "- Annual income: {lead_yearly_wage}\n"
            "- Occupation: {lead_occupation}\n"
            "- Contract length: {lead_contract_length}\n\n"
            "Primary goal by phase:\n"
            "- CONFIRM_INFO: Quickly confirm all required details, then immediately transition to booking a viewing in the same call\n"
            "- BOOKING_VIEWING: Offer and agree a viewing time within viewing hours\n"
            "- VIEWING_BOOKED: Confirm viewing on {viewing_date} at {viewing_time}\n\n"
            "IMPORTANT: In CONFIRM_INFO phase, always progress to viewing booking after confirming details. Don't end the call without attempting to schedule a viewing.\n\n"
            "Guardrails:\n"
            "- One question at a time\n"
            "- Always acknowledge responses before next question\n"
            "- Use their name naturally: {lead_name_fallback}\n"
            "- English only\n"
            "- Immediate greeting when call connects\n"
            "- Stay on topic: booking the viewing\n"
        )

    def build_template_variables(self, lead: Lead) -> Dict[str, Any]:
        """
        Build a mapping of variables used by the general system prompt template.

        Args:
            lead: Lead instance

        Returns:
            Dict with string-safe variables for the template
        """
        # Helpers to safely stringify optional values
        def as_str(value: Any) -> str:
            if value is None:
                return ""
            try:
                return value.value if hasattr(value, "value") else str(value)
            except Exception:
                return str(value)

        # Compute confirmation gaps for CONFIRM_INFO phase
        missing_fields: list[str] = []
        if not getattr(lead, "name", None) or not getattr(lead, "name_confirmed", False):
            missing_fields.append("name")
        if not getattr(lead, "budget", None) or not getattr(lead, "budget_confirmed", False):
            missing_fields.append("budget")
        if not getattr(lead, "move_in_date", None) or not getattr(lead, "move_in_date_confirmed", False):
            missing_fields.append("move-in date")
        if not getattr(lead, "occupation", None) or not getattr(lead, "occupation_confirmed", False):
            missing_fields.append("occupation")
        if not getattr(lead, "yearly_wage", None) or not getattr(lead, "yearly_wage_confirmed", False):
            missing_fields.append("annual income")
        if not getattr(lead, "contract_length", None) or not getattr(lead, "contract_length_confirmed", False):
            missing_fields.append("contract length preference")

        # Price per room calculation (only if both present)
        bedrooms = None
        monthly = None
        price_per_room = ""
        try:
            # These may not exist on Lead; keep flexible if later added
            bedrooms = getattr(lead, "property_bedrooms", None)
            monthly = getattr(lead, "property_monthly_cost", None)
            if bedrooms and monthly and int(bedrooms) > 0:
                price_per_room = str(round(int(monthly) / int(bedrooms)))
        except Exception:
            price_per_room = ""

        # Phase string normalization
        phase_value = lead.phase.value if hasattr(lead.phase, "value") else as_str(lead.phase)

        return {
            "lead_phase": phase_value or "NEW",
            "phase_missing_fields": ", ".join(missing_fields) if missing_fields else "(none)",
            "available_viewing_slots": "weekdays 9:00–17:00",
            "viewing_date": as_str(getattr(lead, "viewing_date", "")),
            "viewing_time": as_str(getattr(lead, "viewing_time", "")),
            "property_address": as_str(getattr(lead, "property_address", "")),
            "property_bedrooms": as_str(bedrooms or ""),
            "property_monthly_cost": as_str(monthly or ""),
            "price_per_room": price_per_room,
            "lead_name": as_str(getattr(lead, "name", "")),
            "lead_phone": as_str(getattr(lead, "phone", "")),
            "lead_budget": as_str(getattr(lead, "budget", "")),
            "lead_move_in_date": as_str(getattr(lead, "move_in_date", "")),
            "lead_yearly_wage": as_str(getattr(lead, "yearly_wage", "")),
            "lead_occupation": as_str(getattr(lead, "occupation", "")),
            "lead_contract_length": as_str(getattr(lead, "contract_length", "")),
            "lead_name_fallback": as_str(getattr(lead, "name", "there")) or "there",
        }

    def render_prompt_template(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Render the system prompt template using Python's format mapping.

        Any placeholder without a provided variable will be replaced with an
        empty string to avoid leaking unresolved tokens to the model.

        Args:
            template: Template string with {placeholders}
            variables: Mapping of values

        Returns:
            Rendered string
        """
        # Use a dict subclass that returns empty string for missing keys
        class SafeDict(dict):
            def __missing__(self, key):  # type: ignore[override]
                return ""

        try:
            return template.format_map(SafeDict(variables))
        except Exception:
            # As a fallback, return the raw template to avoid crashing call flow
            return template

    def build_system_prompt(self, lead: Lead) -> str:
        """
        Build the final system prompt from the general template and lead data.

        Args:
            lead: Lead instance

        Returns:
            Fully rendered system prompt string
        """
        template = self.build_general_system_prompt_template()
        variables = self.build_template_variables(lead)
        return self.render_prompt_template(template, variables)

    def build_agent_url_with_context(self, lead: Lead) -> str:
        """
        Build the ElevenLabs agent URL with context parameters.
        
        Since we can't pre-populate a conversation, we pass
        context through URL parameters that the agent can access.
        
        Args:
            lead: The lead object
            
        Returns:
            Agent URL with context parameters
        """
        
        if not self.agent_url:
            raise ValueError("No ElevenLabs agent URL configured")
        
        # Build query parameters
        params = {
            "lead_id": lead.id,
            # Add any other simple parameters
            # Complex data should use dynamic variables
        }
        
        # Add query string to URL
        query_string = urlencode(params)
        separator = "&" if "?" in self.agent_url else "?"
        
        full_url = f"{self.agent_url}{separator}{query_string}"
        
        logger.info(f"Built agent URL for lead {lead.id}: {full_url}")
        
        return full_url

    async def initiate_outbound_call_via_elevenlabs(self, *, lead: Lead, to_number: str) -> Dict[str, Any]:
        """
        Initiate an outbound phone call via ElevenLabs Telephony.

        Requires settings.elevenlabs_telephony_call_url and elevenlabs_api_key.
        Sends personalization payload inline so ElevenLabs can start immediately.
        """
        if not settings.elevenlabs_telephony_call_url:
            raise ValueError("Missing elevenlabs_telephony_call_url in settings")
        if not settings.elevenlabs_api_key:
            raise ValueError("Missing elevenlabs_api_key in settings")

        # Normalize agent_id in case a URL or '/stream' suffix is provided
        raw_agent_id = (settings.elevenlabs_agent_id or "").strip()
        agent_id_fixed = raw_agent_id
        try:
            if raw_agent_id.startswith("http") or raw_agent_id.startswith("wss"):
                parsed = urlparse(raw_agent_id)
                qs = parse_qs(parsed.query)
                if "agent_id" in qs and qs["agent_id"]:
                    agent_id_fixed = qs["agent_id"][0]
                else:
                    for segment in parsed.path.split('/'):
                        if segment.startswith("agent_"):
                            agent_id_fixed = segment
                            break
            if "/" in agent_id_fixed:
                agent_id_fixed = next((seg for seg in agent_id_fixed.split('/') if seg.startswith("agent_")), agent_id_fixed.split('/')[0])
        except Exception:
            agent_id_fixed = raw_agent_id

        # Minimal required payload for ElevenLabs outbound call
        payload: Dict[str, Any] = {
            "to_number": to_number,
        }

        # Include agent identifier if configured
        if agent_id_fixed:
            payload["agent_id"] = agent_id_fixed
        if settings.elevenlabs_agent_phone_number_id:
            payload["agent_phone_number_id"] = settings.elevenlabs_agent_phone_number_id

        headers = {
            "Content-Type": "application/json",
            "xi-api-key": settings.elevenlabs_api_key,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                settings.elevenlabs_telephony_call_url,
                headers=headers,
                json=payload,
            )
            if resp.status_code >= 300:
                logger.error("ElevenLabs outbound call failed: %s %s", resp.status_code, resp.text)
                raise ValueError("Failed to initiate call via ElevenLabs")

            data = resp.json()
            logger.info("ElevenLabs outbound call initiated for lead %s", lead.id)
            return data

    async def get_signed_conversation_url(self) -> str:
        """
        Obtain a signed WebSocket URL for the ConvAI conversation endpoint.

        This avoids exposing the API key to Twilio by generating a short-lived
        signed URL server-side. Requires `elevenlabs_api_key` and
        `elevenlabs_agent_id` to be configured.

        Returns:
            str: The signed WebSocket URL (wss://...)

        Raises:
            ValueError: If configuration is missing or the API call fails
        """
        if not settings.elevenlabs_agent_id:
            raise ValueError("Missing ElevenLabs agent ID (elevenlabs_agent_id)")
        if not settings.elevenlabs_api_key:
            raise ValueError("Missing ElevenLabs API key (elevenlabs_api_key)")

        # Sanitize/derive a clean agent_id in case a full URL was provided or a suffix was appended
        raw_agent_id = settings.elevenlabs_agent_id.strip()
        agent_id = raw_agent_id
        try:
            if raw_agent_id.startswith("http") or raw_agent_id.startswith("wss"):
                parsed = urlparse(raw_agent_id)
                qs = parse_qs(parsed.query)
                if "agent_id" in qs and qs["agent_id"]:
                    agent_id = qs["agent_id"][0]
                else:
                    # Look for a path segment like 'agent_XXXX'
                    for segment in parsed.path.split('/'):
                        if segment.startswith("agent_"):
                            agent_id = segment
                            break
            # If there is an accidental trailing path like '/stream', remove it
            if "/" in agent_id:
                agent_id = next((seg for seg in agent_id.split('/') if seg.startswith("agent_")), agent_id.split('/')[0])
        except Exception:
            # If anything goes wrong, fall back to the raw value
            agent_id = raw_agent_id

        logger.info(f"Requesting signed ElevenLabs URL for agent_id={agent_id}")

        url = (
            "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url"
            f"?agent_id={agent_id}"
        )
        headers = {"xi-api-key": settings.elevenlabs_api_key}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(
                    "Failed to get signed URL from ElevenLabs (agent_id=%s): %s %s",
                    agent_id,
                    resp.status_code,
                    resp.text,
                )
                # Retry once without the 'agent_' prefix if present
                if agent_id.startswith("agent_"):
                    alt_agent_id = agent_id[len("agent_") :]
                    alt_url = (
                        "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url"
                        f"?agent_id={alt_agent_id}"
                    )
                    logger.info(
                        "Retrying signed URL request with agent_id=%s (no prefix)",
                        alt_agent_id,
                    )
                    resp = await client.get(alt_url, headers=headers)
                    if resp.status_code != 200:
                        logger.error(
                            "Retry failed to get signed URL (agent_id=%s): %s %s",
                            alt_agent_id,
                            resp.status_code,
                            resp.text,
                        )
                        raise ValueError("Failed to get signed URL from ElevenLabs")
                    data = resp.json()
                    signed_url = data.get("signed_url")
                    if not signed_url:
                        raise ValueError("Signed URL missing in ElevenLabs response (retry)")
                    return signed_url
                raise ValueError("Failed to get signed URL from ElevenLabs")
            data = resp.json()
            signed_url = data.get("signed_url")
            if not signed_url:
                raise ValueError("Signed URL missing in ElevenLabs response")
            return signed_url
    
    def get_phase_first_message(self, lead: Lead) -> str:
        """
        Get an appropriate first message based on lead's phase.
        
        Args:
            lead: The lead object
            
        Returns:
            First message for the agent to say
        """
        
        name = lead.name or "there"
        phase = lead.phase.value if hasattr(lead.phase, "value") else lead.phase

        messages = {
            "CONFIRM_INFO": f"Hi {name}! I'm Charlie calling from Lobby about the property you enquired about. I need to confirm a few details before we can book your viewing. Do you have a moment?",
            "BOOKING_VIEWING": f"Hello {name}! I'm calling to help you schedule a property viewing. When would work best for you?",
            "VIEWING_BOOKED": f"Hi {name}, I'm calling to confirm your viewing on {lead.viewing_date or 'the scheduled date'}.",
            "COMPLETED": f"Hello {name}, thank you for your time. Is there anything else I can help you with?",
        }

        return messages.get(phase, f"Hello {name}, how can I assist you today?")
    
    def build_unknown_caller_variables(self, caller_phone: str) -> Dict[str, Any]:
        """Build variables for unknown callers (not in our system)"""
        
        first_message = "Hello! I'm Charlie from Lobby. How can I help you today?"
        
        # Default system prompt for unknown callers - you can edit this
        system_prompt = """You are Charlie from Lobby, a helpful real estate assistant.

You're speaking with someone who called our number but isn't in our system yet.

Your role:
- Be friendly and professional
- Ask how you can help them today
- If they're interested in property rentals, collect their basic details
- If they're calling about something else, try to assist or direct them appropriately

Keep responses brief and natural. Wait for them to explain why they're calling before proceeding.

Important: This caller is not in our current lead system, so treat this as a general inquiry call."""
        
        variables = {
            "first_message": first_message,
            "system_prompt": system_prompt,
            "customer_phone": caller_phone,
            "customer_name": "there",
            "current_phase": "UNKNOWN_CALLER"
        }
        
        return variables