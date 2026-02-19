import re
from typing import Any

from app.config import settings


class PIIService:
    _EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _PHONE_REGEX = re.compile(
        r"\b(?:\(\d{3}\)\s?\d{3}-\d{4}|\d{3}[-.\s]\d{3}[-.\s]\d{4})\b"
    )

    def redact(self, text: str) -> str:
        if settings.pii_redaction_mode == "off":
            return text
        redacted = self._EMAIL_REGEX.sub("[EMAIL]", text)
        redacted = self._PHONE_REGEX.sub("[PHONE]", redacted)
        return redacted

    def redact_dict(self, data: dict) -> dict:
        def _walk(value: Any):
            if isinstance(value, str):
                return self.redact(value)
            if isinstance(value, dict):
                return {k: _walk(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_walk(item) for item in value]
            return value

        return _walk(data)
