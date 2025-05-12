import os
import numpy as np
import torch
import logging
from sentence_transformers import SentenceTransformer
from typing import List
from app.configs.config import app_configs

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Disable flash attention
os.environ["FLASH_ATTENTION_FORCE_DISABLED"] = "1"

class Embedder:
    _instance = None
    _model = None
    _embedding_dim = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Embedder, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize Jina Embeddings V3 model"""
        try:
            config = app_configs.get_embedder_config()
            model_config = config.get("model", {})
            auth_config = config.get("auth", {})
            device_config = config.get("device", {})

            self.model_name = model_config.get("name", "jinaai/jina-embeddings-v3")
            self.hf_token = auth_config.get("huggingface_token")
            
            logger.info(f"Using model: {self.model_name}")
            logger.info(f"Config: {config}")

            if not self.hf_token:
                raise ValueError("HUGGINGFACE_TOKEN not found in config")

            use_cuda = device_config.get("use_cuda", True)
            self.device = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")
            logger.info(f"Using device: {self.device}")

            # Initialize model using sentence-transformers
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                use_auth_token=self.hf_token,
                trust_remote_code=True
            )
            self._embedding_dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"Initialized Embedder with dimension {self._embedding_dim}")

        except Exception as e:
            logger.error(f"Error initializing Embedder: {str(e)}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self._embedding_dim

    def embed_text(self, text: str) -> np.ndarray:
            """Embed a single text string with safety checks and normalization."""
            try:
                text = text.strip()
                if not text:
                    logger.warning("Empty text received for embedding.")
                    return np.zeros(self._embedding_dim)

                embedding = self._model.encode(text, convert_to_numpy=True, truncate=False)

                if embedding.shape != (self._embedding_dim,):
                    logger.warning(f"Unexpected embedding shape: {embedding.shape}")
                    return np.zeros(self._embedding_dim)

                # Normalize vector (cosine similarity requires unit vectors)
                norm = np.linalg.norm(embedding)
                if norm == 0:
                    logger.warning("Embedding vector has zero norm.")
                    return np.zeros(self._embedding_dim)

                return embedding / norm

            except Exception as e:
                logger.error(f"Error embedding text: {str(e)}")
                return np.zeros(self._embedding_dim)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a list of texts with validation and normalization."""
        try:
            clean_texts = [t.strip() if t else "" for t in texts]
            embeddings = self._model.encode(clean_texts, convert_to_numpy=True, truncate=False)

            final_embeddings = []
            for i, emb in enumerate(embeddings):
                if emb.shape != (self._embedding_dim,):
                    logger.warning(f"Invalid shape at index {i}: {emb.shape}")
                    final_embeddings.append(np.zeros(self._embedding_dim))
                    continue

                norm = np.linalg.norm(emb)
                if norm == 0:
                    logger.warning(f"Zero norm at index {i}")
                    final_embeddings.append(np.zeros(self._embedding_dim))
                    continue

                final_embeddings.append(emb / norm)

            return final_embeddings

        except Exception as e:
            logger.error(f"Error embedding batch: {str(e)}")
            return [np.zeros(self._embedding_dim) for _ in texts]