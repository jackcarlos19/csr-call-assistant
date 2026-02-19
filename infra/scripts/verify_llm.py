import asyncio
import os
import sys

sys.path.append(os.getcwd())

from pydantic import BaseModel

from app.config import settings
from app.services.llm_client import LLMClient


class TestSchema(BaseModel):
    sentiment: str
    confidence: float


async def main():
    print(f"Testing LLM Client with model: {settings.llm_primary_model}")
    client = LLMClient()
    messages = [{"role": "user", "content": "The service was terrible and I am angry."}]

    try:
        result = await client.complete(messages, TestSchema)
        print(f"Success! Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
