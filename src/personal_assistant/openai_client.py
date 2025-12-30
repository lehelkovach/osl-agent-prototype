import os
from typing import List, Dict, Optional

from openai import OpenAI


class OpenAIClient:
    """
    Thin wrapper around the OpenAI SDK for chat completions and embeddings.
    Allows dependency injection for easier testing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        chat_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.chat_model = chat_model or os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
        self.embedding_model = embedding_model or os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"
        )

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        response = self.client.chat.completions.create(
            model=self.chat_model, messages=messages, temperature=temperature
        )
        return response.choices[0].message.content

    def embed(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            model=self.embedding_model, input=text
        )
        return response.data[0].embedding


class FakeOpenAIClient:
    """
    Simple fake for tests to avoid network calls.
    """

    def __init__(self, chat_response: str, embedding: Optional[List[float]] = None):
        self.chat_response = chat_response
        self.embedding = embedding or [0.0, 0.0, 0.0]
        self.last_messages: Optional[List[Dict[str, str]]] = None

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        self.last_messages = messages
        return self.chat_response

    def embed(self, text: str) -> List[float]:
        return self.embedding
