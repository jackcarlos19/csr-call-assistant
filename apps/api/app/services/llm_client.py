
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings


class LLMGenerationError(Exception):
    """Raised when LLM generation fails or output cannot be validated."""


class LLMClient:
    """LLM client that enforces structured JSON output via Pydantic schemas."""

    def __init__(self) -> None:
        """Initialize OpenRouter-backed AsyncOpenAI client."""
        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    async def complete(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        """Generate a completion and validate the JSON response against ``schema``."""
        normalized_messages = self._ensure_json_instruction(messages, schema)
        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_primary_model,
                messages=normalized_messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
        except Exception as exc:
            raise LLMGenerationError(f"LLM API request failed: {exc}") from exc

        content = None
        if response.choices:
            content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise LLMGenerationError("LLM returned empty or non-string content")

        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMGenerationError(f"LLM output failed schema validation: {exc}") from exc
        except Exception as exc:
            raise LLMGenerationError(f"LLM output parsing failed: {exc}") from exc

    @staticmethod
    def _ensure_json_instruction(messages: list[dict], schema: type[BaseModel]) -> list[dict]:
        """Ensure request includes explicit JSON and schema-shape instructions."""
        schema_json = schema.model_json_schema()
        properties = schema_json.get("properties", {})
        required_fields = schema_json.get("required", [])
        field_lines = []
        for name, meta in properties.items():
            field_type = meta.get("type", "unknown")
            field_lines.append(f'- "{name}" ({field_type})')

        required_hint = ", ".join(required_fields) if required_fields else "none"
        instruction = {
            "role": "system",
            "content": (
                "Return output as valid JSON only. "
                "Do not include markdown, code fences, or extra commentary.\n"
                f"Match this exact JSON schema shape. Required fields: {required_hint}.\n"
                "Expected fields:\n"
                + ("\n".join(field_lines) if field_lines else "- (no fields)")
            ),
        }
        has_json_hint = any(
            isinstance(message.get("content"), str)
            and "json" in message["content"].lower()
            for message in messages
        )
        if has_json_hint:
            return messages
        return [instruction, *messages]
