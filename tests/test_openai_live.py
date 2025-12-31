import os
from dotenv import load_dotenv

from src.personal_assistant.openai_client import OpenAIClient, FakeOpenAIClient


def test_openai_live_chat_and_embed():
    load_dotenv(".env.local")
    load_dotenv()
    if os.getenv("OPENAI_API_KEY"):
        client = OpenAIClient()
    else:
        client = FakeOpenAIClient(chat_response="Hi", embedding=[0.0] * 10)
    chat = client.chat([{"role": "user", "content": "Say hi briefly"}], temperature=0.0)
    assert isinstance(chat, str)
    assert len(chat.strip()) > 0
    emb = client.embed("test")
    assert isinstance(emb, list)
    assert len(emb) >= 1
