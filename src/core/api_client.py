"""API client for Gemini with streaming support."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Generator

from google import genai
from google.genai import types


def _load_image_part(image_path: str) -> types.Part:
    """Load an image file as a Gemini Part."""
    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    data = Path(image_path).read_bytes()
    return types.Part.from_bytes(data=data, mime_type=mime_type)


class GeminiClient:
    """Google Gemini API client using google-genai SDK."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        image_paths: list[str] | None = None,
    ) -> Generator[str, None, None]:
        """Stream chat completion. Yields text chunks.

        messages: list of {"role": "user"|"assistant", "content": str}
        image_paths: optional list of image file paths to include with the last user message
        """
        contents = []
        for i, msg in enumerate(messages):
            role = "user" if msg["role"] == "user" else "model"
            parts = [types.Part(text=msg["content"])]

            # Attach images to the last user message
            if image_paths and role == "user" and i == len(messages) - 1:
                for img_path in image_paths:
                    try:
                        parts.append(_load_image_part(img_path))
                    except Exception:
                        pass

            contents.append(types.Content(role=role, parts=parts))

        config = types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=8192,
        )
        if system_prompt:
            config.system_instruction = system_prompt

        for chunk in self._client.models.generate_content_stream(
            model=self._model_name,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    def generate_image(self, prompt: str) -> bytes | None:
        """Generate an image using Gemini's image generation.
        Returns PNG bytes or None on failure."""
        try:
            response = self._client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            # Extract image from response
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    return part.inline_data.data
            return None
        except Exception:
            return None

    def chat_sync(
        self,
        messages: list[dict],
        system_prompt: str = "",
    ) -> str:
        result = []
        for chunk in self.stream_chat(messages, system_prompt):
            result.append(chunk)
        return "".join(result)

    def is_available(self) -> bool:
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents="ping",
            )
            return bool(response.text)
        except Exception:
            return False
