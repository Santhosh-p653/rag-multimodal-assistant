import os
import sys
import importlib.util
import logging

# Fix for importlib ValueError: openai.__spec__ is not set when transformers checks package availability
if "openai" in sys.modules and getattr(sys.modules["openai"], "__spec__", None) is None:
    del sys.modules["openai"]

import torch
import threading
from typing import List, Union
from PIL import Image, UnidentifiedImageError
from app.config import settings

logger = logging.getLogger(__name__)


class VisionEmbedderService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._model = None
                cls._instance._processor = None
                cls._instance._device = "cuda" if torch.cuda.is_available() else "cpu"
                cls._instance._model_name = settings.VISION_MODEL
                logger.info("[VisionEmbedder] Initialized singleton wrapper for device: %s", cls._instance._device)
        return cls._instance

    def _load_model(self):
        """Lazy-load SigLIP processor and model only when inference is required."""
        if self._model is None or self._processor is None:
            with self._lock:
                if self._model is None:
                    logger.info("[VisionEmbedder] Loading SigLIP model '%s' on %s...", self._model_name, self._device)
                    import sys
                    import importlib.util
                    if "openai" in sys.modules and getattr(sys.modules["openai"], "__spec__", None) is None:
                        try:
                            spec = importlib.util.find_spec("openai")
                            if spec is not None:
                                sys.modules["openai"].__spec__ = spec
                            else:
                                del sys.modules["openai"]
                        except (AttributeError, KeyError) as exc:
                            # Log but continue — failure here isn't fatal for model loading
                            logger.debug("[VisionEmbedder] Could not fix openai __spec__: %s", exc)

                    from transformers import AutoProcessor, AutoModel

                    # 1. Try loading from local Hugging Face cache first
                    try:
                        self._processor = AutoProcessor.from_pretrained(self._model_name, local_files_only=True)
                        self._model = AutoModel.from_pretrained(self._model_name, local_files_only=True).to(self._device)
                        self._model.eval()
                        logger.info("[VisionEmbedder] SigLIP model loaded from local cache.")
                        return
                    except (OSError, ValueError) as exc:
                        # Local cache not available — fall back to online download
                        logger.debug("[VisionEmbedder] Local model load failed, will try online: %s", exc)

                    # 2. Fallback to online download if not cached
                    orig_hf_offline = os.environ.get("HF_HUB_OFFLINE")
                    orig_tf_offline = os.environ.get("TRANSFORMERS_OFFLINE")
                    if orig_hf_offline == "1":
                        os.environ["HF_HUB_OFFLINE"] = "0"
                    if orig_tf_offline == "1":
                        os.environ["TRANSFORMERS_OFFLINE"] = "0"

                    try:
                        self._processor = AutoProcessor.from_pretrained(self._model_name)
                        self._model = AutoModel.from_pretrained(self._model_name).to(self._device)
                        self._model.eval()
                        logger.info("[VisionEmbedder] SigLIP model ready.")
                    except (OSError, ValueError) as exc:
                        logger.exception("[VisionEmbedder] Failed to load SigLIP model '%s'", self._model_name)
                        raise
                    finally:
                        if orig_hf_offline is not None:
                            os.environ["HF_HUB_OFFLINE"] = orig_hf_offline
                        if orig_tf_offline is not None:
                            os.environ["TRANSFORMERS_OFFLINE"] = orig_tf_offline

    def embed_image(self, image_input: Union[str, Image.Image]) -> List[float]:
        """Embed a single image file path or PIL Image into a normalized float vector."""
        results = self.embed_images([image_input])
        return results[0] if results else []

    def embed_images(self, image_inputs: List[Union[str, Image.Image]]) -> List[List[float]]:
        """
        Embed a batch of image paths or PIL Image instances.
        Returns a list of L2-normalized float vector lists.
        """
        if not image_inputs:
            return []

        try:
            self._load_model()
        except (RuntimeError, OSError) as exc:
            logger.error("[VisionEmbedder] Cannot embed images, model unavailable: %s", exc)
            return []

        pil_images = []
        for img in image_inputs:
            if isinstance(img, str):
                try:
                    loaded = Image.open(img).convert("RGB")
                    pil_images.append(loaded)
                except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
                    logger.warning("[VisionEmbedder] Failed to load image path '%s': %s", img, exc)
                    pil_images.append(Image.new("RGB", (224, 224), color=(0, 0, 0)))
            elif isinstance(img, Image.Image):
                pil_images.append(img.convert("RGB"))
            else:
                raise TypeError(f"Unsupported image type: {type(img)}")

        try:
            with torch.no_grad():
                inputs = self._processor(images=pil_images, return_tensors="pt").to(self._device)
                image_features = self._model.get_image_features(**inputs)
                if not isinstance(image_features, torch.Tensor):
                    if hasattr(image_features, "image_embeds") and image_features.image_embeds is not None:
                        image_features = image_features.image_embeds
                    elif hasattr(image_features, "pooler_output") and image_features.pooler_output is not None:
                        image_features = image_features.pooler_output
                    elif hasattr(image_features, "last_hidden_state"):
                        image_features = image_features.last_hidden_state[:, 0, :]
                    else:
                        image_features = image_features[0]

                image_features = torch.nn.functional.normalize(image_features, dim=-1)
                vectors = image_features.cpu().numpy().tolist()
                return vectors
        except (RuntimeError, ValueError) as exc:
            logger.exception("[VisionEmbedder] Image embedding batch execution failed: %s", exc)
            return []

    def embed_text(self, text: str) -> List[float]:
        """Embed a text string query using SigLIP text encoder into a normalized vector."""
        if not text or not text.strip():
            return []

        try:
            self._load_model()
        except (RuntimeError, OSError) as exc:
            logger.error("[VisionEmbedder] Cannot embed text query, model unavailable: %s", exc)
            return []

        try:
            with torch.no_grad():
                inputs = self._processor(text=[text.strip()], return_tensors="pt", padding=True).to(self._device)
                text_features = self._model.get_text_features(**inputs)
                if not isinstance(text_features, torch.Tensor):
                    if hasattr(text_features, "text_embeds") and text_features.text_embeds is not None:
                        text_features = text_features.text_embeds
                    elif hasattr(text_features, "pooler_output") and text_features.pooler_output is not None:
                        text_features = text_features.pooler_output
                    elif hasattr(text_features, "last_hidden_state"):
                        text_features = text_features.last_hidden_state[:, 0, :]
                    else:
                        text_features = text_features[0]

                text_features = torch.nn.functional.normalize(text_features, dim=-1)
                vector = text_features[0].cpu().numpy().tolist()
                return vector
        except (RuntimeError, ValueError) as exc:
            logger.exception("[VisionEmbedder] Text embedding failed for query '%s': %s", text, exc)
            return []
