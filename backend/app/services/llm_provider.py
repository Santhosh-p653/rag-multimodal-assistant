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
        self.last_fallback_reason: Optional[str] = None
        self.total_requests: int = 0
        self.ollama_served: int = 0
        self.cloud_fallback_served: int = 0

    def _get_ollama_model_for_task(self, task: str, override_model: Optional[str] = None) -> str:
        if override_model:
            return override_model
        task_normalized = (task or "chat").lower().strip()
        if task_normalized in ("classification", "product_id", "classify"):
            return settings.OLLAMA_MODEL_CLASSIFICATION
        elif task_normalized in ("workflow", "troubleshoot", "troubleshooting", "diagnose"):
            return settings.OLLAMA_MODEL_WORKFLOW
        elif task_normalized in ("caption", "captioning", "vision", "image", "image_caption"):
            return getattr(settings, "OLLAMA_MODEL_CAPTION", "gemma3:4b")
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
        images: Optional[list] = None,
        **kwargs: Any,
    ) -> str:
        """
        Unified LLM generation function.
        Tries local Ollama first with task-specific models:
          - classification -> qwen2.5:3b
          - chat           -> llama3.2:3b / gemma3:4b
          - workflow       -> llama3.2:3b
          - caption/vision -> gemma3:4b
        On any failure, falls back automatically to Groq or SambaNova.
        Logs which provider actually served the call and the reason for any fallback.
        """
        self.total_requests += 1
        self.last_task_used = task

        logger.info(f"[LLMProvider] New request for task='{task}' (prompt prefix: {prompt[:60]!r}...)")

        # ─── 1. Attempt Primary: Local Ollama ──────────────────────────────
        if settings.OLLAMA_ENABLED and self.ollama_enabled:
            ollama_model = self._get_ollama_model_for_task(task, override_model=model)
            try:
                # Fast connect timeout (max 5s) to fail fast if Ollama service is not running
                connect_timeout = min(5.0, float(settings.OLLAMA_TIMEOUT_SECONDS))
                read_timeout = float(getattr(settings, "OLLAMA_READ_TIMEOUT_SECONDS", 180.0))
                client_timeout = httpx.Timeout(read_timeout, connect=connect_timeout)

                client = ollama.Client(
                    host=settings.OLLAMA_BASE_URL,
                    timeout=client_timeout,
                )

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})

                user_msg: Dict[str, Any] = {"role": "user", "content": prompt}
                # Support vision/image input for multimodal models like gemma3:4b
                img_list = images or kwargs.get("images")
                if img_list:
                    user_msg["images"] = img_list
                messages.append(user_msg)

                options: Dict[str, Any] = {
                    "num_predict": int(max_tokens) if max_tokens is not None else 1024,
                    "temperature": float(temperature) if temperature is not None else 0.2,
                }

                logger.info(f"[LLMProvider] Attempting local Ollama: model='{ollama_model}', task='{task}'")
                response = client.chat(
                    model=ollama_model,
                    messages=messages,
                    options=options,
                )

                content = response.get("message", {}).get("content", "").strip()
                if content:
                    self.last_provider_used = "ollama"
                    self.last_model_used = ollama_model
                    self.last_error = None
                    self.last_fallback_reason = None
                    self.ollama_served += 1
                    logger.info(f"[LLMProvider] SERVED BY OLLAMA: model='{ollama_model}', task='{task}' ({len(content)} chars)")
                    print(f"[LLMProvider] SERVED BY OLLAMA: model='{ollama_model}', task='{task}' ({len(content)} chars)")
                    return content
                else:
                    self.last_fallback_reason = f"Ollama model {ollama_model} returned empty response"
                    logger.warning(f"[LLMProvider] {self.last_fallback_reason}, falling back...")
                    print(f"[LLMProvider] {self.last_fallback_reason}, falling back...")
            except Exception as exc:
                self.last_error = str(exc)
                self.last_fallback_reason = f"Ollama ({ollama_model}) failed: {exc}"
                logger.warning(
                    "[LLMProvider] FALLBACK TRIGGERED from Ollama (%s) to cloud: %s",
                    ollama_model,
                    exc,
                )
                print(f"[LLMProvider] FALLBACK TRIGGERED from Ollama ({ollama_model}) to cloud: {exc}")
        else:
            self.last_fallback_reason = "Ollama disabled by configuration"
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
                effective_model = cloud_model or getattr(settings, "LLM_MODEL", "") or "qwen/qwen3.8-27b"
                if effective_model == "groq/compound-mini":
                    effective_model = "qwen/qwen3.8-27b"

                logger.info(f"[LLMProvider] Attempting Groq cloud fallback: model='{effective_model}', task='{task}'")
                try:
                    response = client.chat.completions.create(
                        model=effective_model,
                        messages=messages,
                        temperature=temperature if temperature is not None else 0.2,
                        max_tokens=max_tokens if max_tokens is not None else 1024,
                    )
                except Exception as model_err:
                    alt_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"]
                    succeeded = False
                    for alt in alt_models:
                        if alt == effective_model:
                            continue
                        try:
                            logger.warning(f"[LLMProvider] Retrying Groq with alternate model: '{alt}'")
                            response = client.chat.completions.create(
                                model=alt,
                                messages=messages,
                                temperature=temperature if temperature is not None else 0.2,
                                max_tokens=max_tokens if max_tokens is not None else 1024,
                            )
                            effective_model = alt
                            succeeded = True
                            break
                        except Exception:
                            continue
                    if not succeeded:
                        raise model_err

                content = response.choices[0].message.content.strip()
                self.last_provider_used = "groq"
                self.last_model_used = effective_model
                self.cloud_fallback_served += 1
                logger.info(f"[LLMProvider] SERVED BY GROQ FALLBACK: model='{effective_model}', task='{task}' ({len(content)} chars)")
                print(f"[LLMProvider] SERVED BY GROQ FALLBACK: model='{effective_model}', task='{task}' ({len(content)} chars)")
                return content
            except Exception as exc:
                logger.exception("[LLMProvider] Groq cloud fallback failed: %s", exc)
                print(f"[LLMProvider] Groq cloud fallback failed: {exc}")
                if settings.SAMBANOVA_API_KEY:
                    logger.info("[LLMProvider] Attempting secondary fallback to SambaNova...")
                    cloud_provider = "sambanova"
                else:
                    raise

        elif cloud_provider == "sambanova":
            try:
                from openai import OpenAI

                client = OpenAI(
                    api_key=settings.SAMBANOVA_API_KEY,
                    base_url="https://api.sambanova.ai/v1",
                )
                effective_model = cloud_model or "Meta-Llama-3.1-8B-Instruct"
                logger.info(f"[LLMProvider] Attempting SambaNova cloud fallback: model='{effective_model}', task='{task}'")
                response = client.chat.completions.create(
                    model=effective_model,
                    messages=messages,
                    temperature=temperature if temperature is not None else 0.2,
                    max_tokens=max_tokens if max_tokens is not None else 1024,
                )
                content = response.choices[0].message.content.strip()
                self.last_provider_used = "sambanova"
                self.last_model_used = effective_model
                self.cloud_fallback_served += 1
                logger.info(f"[LLMProvider] SERVED BY SAMBANOVA FALLBACK: model='{effective_model}', task='{task}' ({len(content)} chars)")
                print(f"[LLMProvider] SERVED BY SAMBANOVA FALLBACK: model='{effective_model}', task='{task}' ({len(content)} chars)")
                return content
            except Exception as exc:
                logger.exception("[LLMProvider] SambaNova cloud fallback failed: %s", exc)
                print(f"[LLMProvider] SambaNova cloud fallback failed: {exc}")
                raise

        # No provider available
        err_msg = (
            "No LLM provider available. Ollama was unreachable or failed "
            f"({self.last_error or 'disabled'}), and no valid cloud API key "
            "(GROQ_API_KEY or SAMBANOVA_API_KEY) is configured."
        )
        logger.error(f"[LLMProvider] {err_msg}")
        print(f"[LLMProvider] {err_msg}")
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
            "last_fallback_reason": self.last_fallback_reason,
            "task_models": {
                "classification": settings.OLLAMA_MODEL_CLASSIFICATION,
                "chat": settings.OLLAMA_MODEL_CHAT,
                "workflow": settings.OLLAMA_MODEL_WORKFLOW,
                "caption": getattr(settings, "OLLAMA_MODEL_CAPTION", "gemma3:4b"),
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
    images: Optional[list] = None,
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
        images=images,
        **kwargs,
    )


# Backward-compatible alias
call_llm = generate
