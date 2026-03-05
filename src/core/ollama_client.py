"""Ollama SDK wrapper for local model fallback."""

import ollama


class OllamaClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = ollama.Client()
        return cls._instance

    def is_available(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            response = self._client.list()
            return [m.model for m in response.models]
        except Exception:
            return []

    def stream_chat(self, model: str, messages: list[dict], options: dict | None = None):
        """Yield streamed token chunks from ollama.chat."""
        kwargs = {"model": model, "messages": messages, "stream": True}
        if options:
            kwargs["options"] = options
        for chunk in self._client.chat(**kwargs):
            yield chunk
