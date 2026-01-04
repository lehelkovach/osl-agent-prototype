"""
Multi-provider LLM client supporting OpenAI, Anthropic Claude, and Google Gemini.

Supports:
- OpenAI (GPT-4o, GPT-4 Turbo, etc.)
- Anthropic Claude (Claude 3.5 Sonnet, Claude 3 Opus, etc.)
- Google Gemini (Gemini 1.5 Pro, Gemini 1.5 Ultra, etc.)
"""

import os
from typing import List, Dict, Optional, Any, Literal
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send chat messages and get response."""
        pass
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI client (GPT-4o, GPT-4 Turbo, etc.)."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        chat_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        from openai import OpenAI
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


class ClaudeClient(LLMClient):
    """Anthropic Claude client (Claude 3.5 Sonnet, Claude 3 Opus, etc.)."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        chat_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")
        
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.chat_model = chat_model or os.getenv("ANTHROPIC_CHAT_MODEL", "claude-3-5-sonnet-20241022")
        self.embedding_model = embedding_model  # Claude doesn't have separate embedding API
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            # Convert messages format (Claude uses different format)
            system_message = None
            claude_messages = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    system_message = content
                else:
                    # Claude uses "user" and "assistant" roles
                    claude_role = "user" if role == "user" else "assistant"
                    claude_messages.append({"role": claude_role, "content": content})
            
            # Claude API call
            response = self.client.messages.create(
                model=self.chat_model,
                max_tokens=4096,
                temperature=temperature,
                system=system_message if system_message else None,
                messages=claude_messages,
            )
            
            # Extract text from response
            if response.content and len(response.content) > 0:
                return response.content[0].text
            return ""
        except Exception as exc:
            raise RuntimeError(f"Claude chat failed: {exc}") from exc
    
    def embed(self, text: str) -> List[float]:
        # Claude doesn't have a separate embedding API
        # Fall back to OpenAI embeddings or local embeddings
        raise NotImplementedError("Claude doesn't provide embeddings. Use OpenAI or local embeddings.")


class GeminiClient(LLMClient):
    """Google Gemini client (Gemini 1.5 Pro, Gemini 1.5 Ultra, etc.)."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        chat_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package required. Install with: pip install google-generativeai")
        
        api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        
        self.chat_model = chat_model or os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-pro")
        self.embedding_model = embedding_model or os.getenv("GEMINI_EMBEDDING_MODEL", "models/embedding-001")
        self.genai = genai
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            model = self.genai.GenerativeModel(self.chat_model)
            
            # Convert messages to Gemini format
            # Gemini uses a different message format
            conversation = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    # Gemini doesn't have system messages, prepend to first user message
                    if not conversation:
                        content = f"System: {content}\n\nUser: "
                    else:
                        continue
                elif role == "user":
                    conversation.append({"role": "user", "parts": [content]})
                elif role == "assistant":
                    conversation.append({"role": "model", "parts": [content]})
            
            # Start chat session
            chat = model.start_chat(history=conversation[:-1] if len(conversation) > 1 else [])
            
            # Get response
            last_message = conversation[-1]["parts"][0] if conversation else ""
            response = chat.send_message(last_message, generation_config={
                "temperature": temperature,
            })
            
            return response.text
        except Exception as exc:
            raise RuntimeError(f"Gemini chat failed: {exc}") from exc
    
    def embed(self, text: str) -> List[float]:
        try:
            result = self.genai.embed_content(
                model=self.embedding_model,
                content=text,
            )
            return result['embedding']
        except Exception as exc:
            raise RuntimeError(f"Gemini embed failed: {exc}") from exc


def create_llm_client(
    provider: Optional[Literal["openai", "claude", "gemini"]] = None,
    api_key: Optional[str] = None,
    chat_model: Optional[str] = None,
    embedding_model: Optional[str] = None,
) -> LLMClient:
    """
    Factory function to create an LLM client based on provider.
    
    Args:
        provider: "openai", "claude", or "gemini". If None, uses LLM_PROVIDER env var.
        api_key: API key (overrides env var)
        chat_model: Chat model name (overrides env var)
        embedding_model: Embedding model name (overrides env var)
    
    Returns:
        LLMClient instance
    """
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider == "openai":
        return OpenAIClient(api_key=api_key, chat_model=chat_model, embedding_model=embedding_model)
    elif provider == "claude":
        return ClaudeClient(api_key=api_key, chat_model=chat_model, embedding_model=embedding_model)
    elif provider == "gemini":
        return GeminiClient(api_key=api_key, chat_model=chat_model, embedding_model=embedding_model)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'openai', 'claude', or 'gemini'")
