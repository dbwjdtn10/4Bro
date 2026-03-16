"""AI Engine manager: Gemini-only."""

from __future__ import annotations

import json
import os
from typing import Generator

from core.api_client import GeminiClient


class EngineStatus:
    """Tracks usage counts and availability."""

    def __init__(self):
        self.gemini_available: bool = False
        self.gemini_count: int = 0
        self.gemini_daily_limit: int = 250


class AIEngine:
    """Manages Gemini AI engine."""

    def __init__(self):
        self._gemini: GeminiClient | None = None
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

            if gemini_key:
                self._gemini = GeminiClient(gemini_key)
                self.status.gemini_available = True
        except Exception:
            pass

    def save_config(self, gemini_key: str = ""):
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

        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        if gemini_key:
            self._gemini = GeminiClient(gemini_key)
            self.status.gemini_available = True

    def setup_gemini(self, api_key: str):
        self._gemini = GeminiClient(api_key)
        self.status.gemini_available = True
        self.save_config(gemini_key=api_key)

    def get_saved_keys(self) -> dict[str, str]:
        """Return saved API keys from config (raw values)."""
        if not os.path.exists(self._config_path):
            return {}
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return {
                "gemini": config.get("gemini_api_key", ""),
            }
        except Exception:
            return {}

    def get_current_engine_name(self) -> str:
        return "Gemini API"

    def get_usage_text(self) -> str:
        return f"{self.status.gemini_count}/{self.status.gemini_daily_limit}"

    @property
    def gemini_client(self) -> GeminiClient | None:
        return self._gemini

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        image_paths: list[str] | None = None,
    ) -> Generator[str, None, None]:
        """Stream chat using Gemini. Yields text chunks."""
        if not self._gemini:
            raise RuntimeError(
                "Gemini API key not configured.\n"
                "Please set your API key in Settings."
            )

        for chunk in self._gemini.stream_chat(messages, system_prompt, image_paths):
            yield chunk

        self.status.gemini_count += 1

    def generate_image(self, prompt: str) -> bytes | None:
        """Generate an image using Gemini. Returns PNG bytes or None."""
        if not self._gemini:
            return None
        return self._gemini.generate_image(prompt)

    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self.status.gemini_available and self._gemini is not None
