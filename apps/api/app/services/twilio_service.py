import structlog
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import settings

logger = structlog.get_logger()


class TwilioService:
    def __init__(self) -> None:
        self.validator = (
            RequestValidator(settings.twilio_auth_token) if settings.twilio_auth_token else None
        )

    def validate_signature(self, url: str, form_data: dict, signature: str | None) -> bool:
        if self.validator is None:
            logger.warning("twilio_signature_validation_skipped", reason="missing_auth_token")
            return True
        if not signature:
            return False
        return self.validator.validate(url, form_data, signature)

    def build_stream_twiml(self, stream_url: str, session_id: str) -> str:
        response = VoiceResponse()
        response.say("Connecting you to Comfort Air Services assistant.", voice="alice")
        connect = Connect()
        connect.stream(url=stream_url, name=f"session-{session_id}")
        response.append(connect)
        return str(response)
