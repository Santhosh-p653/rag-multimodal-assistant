"""
llm_provider.py — Unified LLM Provider with automatic local-to-cloud fallback.

Routes LLM requests to local Ollama (primary) with task-specific models:
  - classification -> qwen2.5:3b (zero-shot document/product identification)
  - chat           -> gemma3:4b (main RAG Q&A)
  - workflow       -> llama3.2:3b (troubleshooting state machine & reasoning)

Falls back automatically to cloud providers (Groq / SambaNova) if Ollama
is unreachable, times out, or returns an error.
"""

import logging
import threading
from typing import Optional, Dict, Any
import httpx
import ollama
from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_provider()
        return cls._instance

    def _init_provider(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS
        self.ollama_enabled = settings.OLLAMA_ENABLED

        # State tracking
        self.last_provider_used: str = "none"
        self.last_model_used: str = ""
        self.last_task_used: str = ""
        self.last_error: Optional[str] = None
        self.total_requests: int = 0
        self.ollama_served: int = 0
        self.cloud_fallback_served: int = 0

    def _get_ollama_model_for_task(self, task: str, override_model: Optional[str] = None) -> str:
        if override_model:
            return override_model
        task_normalized = (task or "chat").lower().strip()
        if task_normalized == "classification":
            return settings.OLLAMA_MODEL_CLASSIFICATION
        elif task_normalized == "workflow":
            return settings.OLLAMA_MODEL_WORKFLOW
        else:
            return settings.OLLAMA_MODEL_CHAT

    def generate(
        self,
        prompt: str,
        task: str = "chat",
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Unified LLM generation function.
        Tries local Ollama first. On any failure, falls back to Groq or SambaNova.
        """
        self.total_requests += 1
        self.last_task_used = task

        # ─── 1. Attempt Primary: Local Ollama ──────────────────────────────
        if settings.OLLAMA_ENABLED and self.ollama_enabled:
            ollama_model = self._get_ollama_model_for_task(task, override_model=model)
            try:
                # Use connection timeout to fail fast if Ollama service is not running
                connect_timeout = float(settings.OLLAMA_TIMEOUT_SECONDS)
                read_timeout = float(getattr(settings, "OLLAMA_READ_TIMEOUT_SECONDS", 180.0))
                client_timeout = httpx.Timeout(read_timeout, connect=connect_timeout)

                client = ollama.Client(
                    host=settings.OLLAMA_BASE_URL,
                    timeout=client_timeout,
                )

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                options: Dict[str, Any] = {}
                if temperature is not None:
                    options["temperature"] = float(temperature)
                if max_tokens is not None:
                    options["num_predict"] = int(max_tokens)

                response = client.chat(
                    model=ollama_model,
                    messages=messages,
                    options=options if options else None,
                )

                content = response.get("message", {}).get("content", "").strip()
                if content:
                    self.last_provider_used = "ollama"
                    self.last_model_used = ollama_model
                    self.last_error = None
                    self.ollama_served += 1
                    return content
                else:
                    logger.warning("[LLMProvider] Ollama returned empty response, falling back...")
            except Exception as exc:
                self.last_error = str(exc)
                logger.warning(
                    "[LLMProvider] Ollama unavailable (%s), falling back to cloud provider: %s",
                    ollama_model,
                    exc,
                )
        else:
            logger.debug("[LLMProvider] Ollama disabled by configuration, routing to cloud.")

        # ─── 2. Automatic Cloud Fallback (Groq / SambaNova) ─────────────────
        cloud_provider = getattr(settings, "LLM_PROVIDER", "none")
        cloud_model = getattr(settings, "LLM_MODEL", "")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if cloud_provider == "groq":
            try:
                from groq import Groq

                client = Groq(api_key=settings.GROQ_API_KEY)
                response = client.chat.completions.create(
                    model=cloud_model or "groq/compound-mini",
                    messages=messages,
                    temperature=temperature if temperature is not None else 0.2,
                    max_tokens=max_tokens if max_tokens is not None else 1024,
                )
                self.last_provider_used = "groq"
                self.last_model_used = cloud_model
                self.cloud_fallback_served += 1
                return response.choices[0].message.content.strip()
            except Exception as exc:
                logger.exception("[LLMProvider] Groq cloud fallback failed: %s", exc)
                raise

        elif cloud_provider == "sambanova":
            try:
                from openai import OpenAI

                client = OpenAI(
                    api_key=settings.SAMBANOVA_API_KEY,
                    base_url="https://api.sambanova.ai/v1",
                )
                response = client.chat.completions.create(
                    model=cloud_model or "Meta-Llama-3.1-8B-Instruct",
                    messages=messages,
                    temperature=temperature if temperature is not None else 0.2,
                    max_tokens=max_tokens if max_tokens is not None else 1024,
                )
                self.last_provider_used = "sambanova"
                self.last_model_used = cloud_model
                self.cloud_fallback_served += 1
                return response.choices[0].message.content.strip()
            except Exception as exc:
                logger.exception("[LLMProvider] SambaNova cloud fallback failed: %s", exc)
                raise

        # No provider available
        err_msg = (
            "No LLM provider available. Ollama was unreachable or failed "
            f"({self.last_error or 'disabled'}), and no valid cloud API key "
            "(GROQ_API_KEY or SAMBANOVA_API_KEY) is configured."
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive status for /health/llm diagnostics."""
        ollama_reachable = False
        try:
            client = ollama.Client(
                host=settings.OLLAMA_BASE_URL,
                timeout=min(2.0, settings.OLLAMA_TIMEOUT_SECONDS),
            )
            client.list()
            ollama_reachable = True
        except Exception:
            ollama_reachable = False

        return {
            "status": "ok",
            "primary_provider": "ollama",
            "ollama_enabled": bool(settings.OLLAMA_ENABLED and self.ollama_enabled),
            "ollama_base_url": settings.OLLAMA_BASE_URL,
            "ollama_reachable": ollama_reachable,
            "cloud_fallback_provider": settings.LLM_PROVIDER,
            "cloud_fallback_model": settings.LLM_MODEL,
            "last_provider_used": self.last_provider_used,
            "last_model_used": self.last_model_used,
            "last_task": self.last_task_used,
            "last_error": self.last_error,
            "task_models": {
                "classification": settings.OLLAMA_MODEL_CLASSIFICATION,
                "chat": settings.OLLAMA_MODEL_CHAT,
                "workflow": settings.OLLAMA_MODEL_WORKFLOW,
            },
            "stats": {
                "total_requests": self.total_requests,
                "ollama_served": self.ollama_served,
                "cloud_fallback_served": self.cloud_fallback_served,
            },
        }


# Singleton instance and convenience entrypoint
llm_provider = LLMProvider()


def generate(
    prompt: str,
    task: str = "chat",
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Convenience module-level interface for unified LLM calls."""
    return llm_provider.generate(
        prompt=prompt,
        task=task,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        **kwargs,
    )
