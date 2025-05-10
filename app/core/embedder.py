import os
import numpy as np
import torch
import logging
from transformers import AutoTokenizer, AutoModel
from typing import List
from app.configs.config import app_configs

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Embedder:
    _instance = None
    _model = None
    _tokenizer = None
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
            self.trust_remote_code = model_config.get("trust_remote_code", True)
            self.hf_token = auth_config.get("huggingface_token")
            
            if not self.hf_token:
                raise ValueError("HUGGINGFACE_TOKEN not found in config")

            use_cuda = device_config.get("use_cuda", True)
            self.device = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")
            logger.info(f"Using device: {self.device}")

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                token=self.hf_token
            )
            self._model = AutoModel.from_pretrained(
                self.model_name,
                token=self.hf_token,
                trust_remote_code=self.trust_remote_code
            ).to(self.device)
            self._model.eval()
            self._embedding_dim = self._model.config.hidden_size
            logger.info(f"Initialized Embedder with dimension {self._embedding_dim}")

        except Exception as e:
            logger.error(f"Error initializing Embedder: {str(e)}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self._embedding_dim

    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling with attention mask"""
        try:
            token_embeddings = model_output[0]
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = input_mask_expanded.sum(1).clamp(min=1e-9)
            mean_embeddings = sum_embeddings / sum_mask
            return mean_embeddings
        except Exception as e:
            logger.error(f"Error in mean pooling: {str(e)}")
            raise

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string"""
        try:
            encoded_input = self._tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(self.device)
            with torch.no_grad():
                model_output = self._model(**encoded_input)
            embedding = self._mean_pooling(model_output, encoded_input["attention_mask"])
            embedding_np = embedding[0].detach().cpu().numpy()

            if embedding_np.shape != (self._embedding_dim,):
                logger.warning(f"Invalid embedding shape: {embedding_np.shape}")
                return np.zeros(self._embedding_dim)

            return embedding_np
        except Exception as e:
            logger.error(f"Error embedding text: {str(e)}")
            return np.zeros(self._embedding_dim)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a list of texts"""
        try:
            encoded_input = self._tokenizer(texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
            with torch.no_grad():
                model_output = self._model(**encoded_input)
            embeddings = self._mean_pooling(model_output, encoded_input["attention_mask"])
            embeddings_np = embeddings.detach().cpu().numpy()

            final_embeddings = []
            for emb in embeddings_np:
                if emb.shape != (self._embedding_dim,):
                    logger.warning(f"Invalid embedding shape: {emb.shape}")
                    final_embeddings.append(np.zeros(self._embedding_dim))
                else:
                    final_embeddings.append(emb)

            return final_embeddings
        except Exception as e:
            logger.error(f"Error embedding batch: {str(e)}")
            return [np.zeros(self._embedding_dim) for _ in texts] 