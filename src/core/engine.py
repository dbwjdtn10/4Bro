"""AI Engine manager: 3-stage fallback (Gemini -> Groq -> Ollama)."""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import Generator

from core.api_client import GeminiClient, GroqClient


class EngineType(Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    OLLAMA = "ollama"


class EngineStatus:
    """Tracks usage counts and availability for each engine."""

    def __init__(self):
        self.current: EngineType = EngineType.GEMINI
        self.gemini_available: bool = False
        self.groq_available: bool = False
        self.ollama_available: bool = False
        self.gemini_count: int = 0
        self.groq_count: int = 0
        self.ollama_count: int = 0
        self.gemini_daily_limit: int = 250
        self.groq_daily_limit: int = 14400


class AIEngine:
    """Manages 3-stage AI engine with automatic fallback.

    Priority: Gemini API -> Groq API -> Local Ollama
    """

    def __init__(self):
        self._gemini: GeminiClient | None = None
        self._groq: GroqClient | None = None
        self._ollama_model: str = ""
        self.status = EngineStatus()
        self._config_path = os.path.join(
            os.path.expanduser("~"), "Documents", "4Bro", "config.json"
        )
        self._load_config()

    def _load_config(self):
        if not os.path.exists(self._config_path):
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            gemini_key = config.get("gemini_api_key", "")
            groq_key = config.get("groq_api_key", "")
            self._ollama_model = config.get("ollama_model", "qwen2.5:14b")

            if gemini_key:
                self._gemini = GeminiClient(gemini_key)
                self.status.gemini_available = True
            if groq_key:
                self._groq = GroqClient(groq_key)
                self.status.groq_available = True
        except Exception:
            pass

    def save_config(self, gemini_key: str = "", groq_key: str = "", ollama_model: str = ""):
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        config = {}
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                pass

        if gemini_key:
            config["gemini_api_key"] = gemini_key
        if groq_key:
            config["groq_api_key"] = groq_key
        if ollama_model:
            config["ollama_model"] = ollama_model

        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        if gemini_key:
            self._gemini = GeminiClient(gemini_key)
            self.status.gemini_available = True
        if groq_key:
            self._groq = GroqClient(groq_key)
            self.status.groq_available = True
        if ollama_model:
            self._ollama_model = ollama_model

    def setup_gemini(self, api_key: str):
        self._gemini = GeminiClient(api_key)
        self.status.gemini_available = True
        self.save_config(gemini_key=api_key)

    def setup_groq(self, api_key: str):
        self._groq = GroqClient(api_key)
        self.status.groq_available = True
        self.save_config(groq_key=api_key)

    def get_saved_keys(self) -> dict[str, str]:
        """Return saved API keys from config (raw values)."""
        if not os.path.exists(self._config_path):
            return {}
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return {
                "gemini": config.get("gemini_api_key", ""),
                "groq": config.get("groq_api_key", ""),
            }
        except Exception:
            return {}

    def check_ollama(self) -> bool:
        try:
            from core.ollama_client import OllamaClient
            client = OllamaClient()
            self.status.ollama_available = client.is_available()
            return self.status.ollama_available
        except Exception:
            self.status.ollama_available = False
            return False

    def get_current_engine_name(self) -> str:
        names = {
            EngineType.GEMINI: "Gemini API",
            EngineType.GROQ: "Groq API",
            EngineType.OLLAMA: "Local Ollama",
        }
        return names.get(self.status.current, "Unknown")

    def get_usage_text(self) -> str:
        if self.status.current == EngineType.GEMINI:
            return f"{self.status.gemini_count}/{self.status.gemini_daily_limit}"
        elif self.status.current == EngineType.GROQ:
            return f"{self.status.groq_count}/{self.status.groq_daily_limit}"
        return "unlimited"

    @property
    def gemini_client(self) -> GeminiClient | None:
        return self._gemini

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        image_paths: list[str] | None = None,
    ) -> Generator[str, None, None]:
        """Stream chat with automatic fallback. Yields text chunks."""
        engines_to_try = self._get_engine_order()

        # If images are attached, prefer Gemini (only engine that supports images)
        if image_paths:
            if EngineType.GEMINI in engines_to_try:
                engines_to_try = [EngineType.GEMINI] + [
                    e for e in engines_to_try if e != EngineType.GEMINI
                ]

        last_error = None
        for engine_type in engines_to_try:
            had_tokens = False
            try:
                for chunk in self._stream_with_engine(
                    engine_type, messages, system_prompt, image_paths
                ):
                    had_tokens = True
                    yield chunk
                self.status.current = engine_type
                self._increment_count(engine_type)
                return
            except Exception as e:
                last_error = e
                if had_tokens:
                    # Already yielded partial tokens — fallback would corrupt output
                    raise
                continue

        raise RuntimeError(
            f"All engines failed. Last error: {last_error}\n"
            "Please check your API keys or Ollama installation."
        )

    def _get_engine_order(self) -> list[EngineType]:
        order = []
        if self.status.gemini_available and self._gemini:
            order.append(EngineType.GEMINI)
        if self.status.groq_available and self._groq:
            order.append(EngineType.GROQ)
        if self.status.ollama_available:
            order.append(EngineType.OLLAMA)
        if not order:
            order.append(EngineType.GEMINI)
        return order

    def _stream_with_engine(
        self,
        engine_type: EngineType,
        messages: list[dict],
        system_prompt: str,
        image_paths: list[str] | None = None,
    ) -> Generator[str, None, None]:
        if engine_type == EngineType.GEMINI:
            if not self._gemini:
                raise RuntimeError("Gemini API key not configured")
            yield from self._gemini.stream_chat(messages, system_prompt, image_paths)

        elif engine_type == EngineType.GROQ:
            if not self._groq:
                raise RuntimeError("Groq API key not configured")
            yield from self._groq.stream_chat(messages, system_prompt)

        elif engine_type == EngineType.OLLAMA:
            yield from self._stream_ollama(messages, system_prompt)

    def _stream_ollama(
        self, messages: list[dict], system_prompt: str
    ) -> Generator[str, None, None]:
        from core.ollama_client import OllamaClient
        client = OllamaClient()
        ollama_messages = []
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            ollama_messages.append({"role": msg["role"], "content": msg["content"]})

        model = self._ollama_model or "qwen2.5:14b"
        for chunk in client.stream_chat(model, ollama_messages):
            token = chunk.message.content
            if token:
                yield token

    def _increment_count(self, engine_type: EngineType):
        if engine_type == EngineType.GEMINI:
            self.status.gemini_count += 1
        elif engine_type == EngineType.GROQ:
            self.status.groq_count += 1
        elif engine_type == EngineType.OLLAMA:
            self.status.ollama_count += 1
