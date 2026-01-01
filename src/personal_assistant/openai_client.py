import os
from typing import List, Dict, Optional, Any

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

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )
            return response.choices[0].message.content
        except Exception as exc:
            # Surface headers/status if available
            err_data = getattr(exc, "response", None)
            meta = {}
            if err_data is not None:
                meta["status"] = getattr(err_data, "status_code", None)
                meta["headers"] = dict(getattr(err_data, "headers", {}) or {})
            raise RuntimeError(f"OpenAI chat failed: {exc} meta={meta}") from exc

    def embed(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model, input=text
            )
            return response.data[0].embedding
        except Exception as exc:
            err_data = getattr(exc, "response", None)
            meta = {}
            if err_data is not None:
                meta["status"] = getattr(err_data, "status_code", None)
                meta["headers"] = dict(getattr(err_data, "headers", {}) or {})
            raise RuntimeError(f"OpenAI embed failed: {exc} meta={meta}") from exc


class FakeOpenAIClient:
    """
    Simple fake for tests to avoid network calls.
    """

    def __init__(self, chat_response: str, embedding: Optional[List[float]] = None):
        self.chat_response = chat_response
        self.embedding = embedding or [0.0, 0.0, 0.0]
        self.last_messages: Optional[List[Dict[str, str]]] = None
        self.last_response_format: Optional[Dict[str, Any]] = None
        self.last_temperature: Optional[float] = None

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0, response_format: Optional[Dict[str, Any]] = None) -> str:
        self.last_messages = messages
        self.last_response_format = response_format
        self.last_temperature = temperature
        return self.chat_response

    def embed(self, text: str) -> List[float]:
        return self.embedding
