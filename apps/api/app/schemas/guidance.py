from pydantic import BaseModel, Field, field_validator


class GuidanceResponse(BaseModel):
    suggested_reply: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


class CallSummaryResponse(BaseModel):
    summary: str
    disposition: str

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value):
        if isinstance(value, list):
            lines = [str(item).strip() for item in value if str(item).strip()]
            return "\n".join(f"- {line}" for line in lines)
        return value
