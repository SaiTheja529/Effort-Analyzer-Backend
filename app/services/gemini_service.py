from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


MODEL_FALLBACKS: tuple[str, ...] = (
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
    "gemma-3-4b-it",
    "gemma-3-1b-it",
)
XAI_MODEL_FALLBACKS: tuple[str, ...] = (
    "grok-3-fast-latest",
    "grok-3-latest",
    "grok-3-fast",
    "grok-3",
)
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 20.0


class GeminiService:
    """
    Primary Gemini generator with automatic Grok (xAI) fallback.
    """

    def __init__(self):
        self.gemini_api_key = (settings.GEMINI_API_KEY or "").strip()
        self.gemini_model = settings.GEMINI_MODEL

        self.xai_api_key = (settings.XAI_API_KEY or "").strip()
        self.xai_model = settings.XAI_MODEL
        self.xai_base_url = settings.XAI_BASE_URL.rstrip("/")

        if self.xai_api_key.lower().startswith("gsk_"):
            raise RuntimeError(
                "XAI_API_KEY looks like a Groq key (gsk_*). "
                "Use a valid xAI key from https://console.x.ai for Grok fallback."
            )

        # Backward-compatible field used in existing logs/scripts.
        self.model = self.gemini_model if self.gemini_api_key else self.xai_model

        if not self.gemini_api_key and not self.xai_api_key:
            raise RuntimeError("Neither GEMINI_API_KEY nor XAI_API_KEY is configured.")

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for name in values:
            if name and name not in deduped:
                deduped.append(name)
        return deduped

    def _gemini_model_candidates(self) -> list[str]:
        # Keep configured model first, then stable fallbacks.
        return self._dedupe([self.gemini_model, *MODEL_FALLBACKS])

    def _xai_model_candidates(self) -> list[str]:
        return self._dedupe([self.xai_model, *XAI_MODEL_FALLBACKS])

    def _extract_gemini_text(self, response_json: dict[str, Any]) -> str:
        chunks: list[str] = []
        for candidate in response_json.get("candidates", []) or []:
            content = candidate.get("content", {}) or {}
            for part in content.get("parts", []) or []:
                piece = part.get("text")
                if piece:
                    chunks.append(piece)

        return "\n".join(chunks).strip() if chunks else ""

    def _extract_xai_text(self, response_json: dict[str, Any]) -> str:
        for choice in response_json.get("choices", []) or []:
            message = choice.get("message", {}) or {}
            content = message.get("content")

            if isinstance(content, str) and content.strip():
                return content.strip()

            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if text:
                            parts.append(text)
                if parts:
                    return "\n".join(parts).strip()

        return ""

    def _build_error(
        self,
        provider: str,
        model_name: str,
        response: httpx.Response,
    ) -> RuntimeError:
        message = response.text
        try:
            payload = response.json()
            if isinstance(payload.get("error"), dict):
                message = payload.get("error", {}).get("message", message)
            elif isinstance(payload.get("message"), str):
                message = payload.get("message") or message
        except Exception:
            pass
        return RuntimeError(
            f"{provider} API error for model '{model_name}': {response.status_code} {message}"
        )

    def _should_try_next_model(self, status_code: int, err: RuntimeError) -> bool:
        message = str(err).lower()
        non_retryable_markers = (
            "api key not valid",
            "incorrect api key",
            "invalid api key",
            "permission denied",
        )
        if any(marker in message for marker in non_retryable_markers):
            return False

        if status_code in {404, 429, 500, 502, 503, 504}:
            return True

        retry_markers = (
            "not found",
            "unsupported",
            "invalid argument",
            "does not exist",
            "quota exceeded",
            "rate limit",
            "resource exhausted",
            "high demand",
            "unavailable",
            "try again later",
            "overloaded",
            "temporarily",
        )
        return any(marker in message for marker in retry_markers)

    def _generate_with_gemini(self, prompt: str) -> str:
        if not self.gemini_api_key:
            raise RuntimeError("Gemini key not configured.")

        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ]
        }

        last_error: Exception | None = None

        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            for model_name in self._gemini_model_candidates():
                url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent"
                try:
                    response = client.post(
                        url,
                        params={"key": self.gemini_api_key},
                        json=body,
                    )
                except httpx.TimeoutException as exc:
                    last_error = RuntimeError(
                        f"Gemini request timed out after {REQUEST_TIMEOUT_SECONDS}s"
                    )
                    break
                except httpx.RequestError as exc:
                    last_error = RuntimeError(f"Gemini network error: {exc}")
                    break

                if response.status_code == 200:
                    text = self._extract_gemini_text(response.json())
                    return text if text else "No response"

                current_error = self._build_error("Gemini", model_name, response)
                last_error = current_error

                if self._should_try_next_model(response.status_code, current_error):
                    continue

                break

        raise RuntimeError(f"Gemini generation failed: {last_error}") from last_error

    def _generate_with_xai(self, prompt: str) -> str:
        if not self.xai_api_key:
            raise RuntimeError("XAI_API_KEY is not configured.")

        last_error: Exception | None = None
        url = f"{self.xai_base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.xai_api_key}"}

        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            for model_name in self._xai_model_candidates():
                body = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                }

                try:
                    response = client.post(url, headers=headers, json=body)
                except httpx.TimeoutException as exc:
                    last_error = RuntimeError(
                        f"Grok request timed out after {REQUEST_TIMEOUT_SECONDS}s"
                    )
                    break
                except httpx.RequestError as exc:
                    last_error = RuntimeError(f"Grok network error: {exc}")
                    break

                if response.status_code == 200:
                    text = self._extract_xai_text(response.json())
                    return text if text else "No response"

                current_error = self._build_error("Grok", model_name, response)
                last_error = current_error

                if self._should_try_next_model(response.status_code, current_error):
                    continue

                break

        raise RuntimeError(f"Grok generation failed: {last_error}") from last_error

    def generate(self, prompt: str) -> str:
        provider_errors: list[str] = []

        if self.gemini_api_key:
            try:
                return self._generate_with_gemini(prompt)
            except Exception as exc:
                provider_errors.append(str(exc))

        if self.xai_api_key:
            try:
                return self._generate_with_xai(prompt)
            except Exception as exc:
                provider_errors.append(str(exc))

        if provider_errors:
            raise RuntimeError("AI generation failed: " + " | ".join(provider_errors))

        raise RuntimeError("No AI provider key configured.")
