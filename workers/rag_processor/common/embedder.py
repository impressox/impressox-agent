import os
import numpy as np
import torch
import logging
from transformers import AutoTokenizer, AutoModel
from typing import List, Union
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

os.environ["FLASH_ATTENTION_FORCE_DISABLED"] = "1"

import os
import numpy as np
import torch
import logging
from transformers import AutoTokenizer, AutoModel
from typing import List
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

os.environ["FLASH_ATTENTION_FORCE_DISABLED"] = "1"

class JinaEmbedder:
    def __init__(self):
        """Initialize Jina Embeddings V3 model"""
        self.model_name = "jinaai/jina-embeddings-v3"
        self.hf_token = os.getenv("HUGGINGFACE_TOKEN")
        if not self.hf_token:
            raise ValueError("HUGGINGFACE_TOKEN environment variable is not set")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                token=self.hf_token
            )
            self.model = AutoModel.from_pretrained(
                self.model_name,
                token=self.hf_token,
                trust_remote_code=True
            ).to(self.device)
            self.model.eval()
            self.embedding_dim = self.model.config.hidden_size
            logger.info(f"Initialized JinaEmbedder with dimension {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Error initializing JinaEmbedder: {str(e)}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self.embedding_dim

    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling with attention mask"""
        try:
            token_embeddings = model_output[0]  # shape: (batch_size, seq_len, hidden_size)
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = input_mask_expanded.sum(1).clamp(min=1e-9)
            mean_embeddings = sum_embeddings / sum_mask
            return mean_embeddings
        except Exception as e:
            logger.error(f"Error in mean pooling: {str(e)}")
            raise

    def _validate_embedding(self, embedding: np.ndarray) -> bool:
        """Validate embedding shape and values"""
        try:
            if embedding.shape != (self.embedding_dim,):
                logger.warning(f"Invalid embedding shape: {embedding.shape}, expected ({self.embedding_dim},)")
                return False
            if np.isnan(embedding).any() or np.isinf(embedding).any():
                logger.error("Embedding contains NaN or Inf values")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating embedding: {str(e)}")
            return False

    def _reshape_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """Ensure correct shape and size of the embedding"""
        try:
            if embedding.ndim > 1:
                embedding = np.mean(embedding, axis=0)
            if embedding.size != self.embedding_dim:
                logger.warning(f"Resizing embedding from {embedding.size} to {self.embedding_dim}")
                embedding = embedding[:self.embedding_dim] if embedding.size > self.embedding_dim else np.pad(
                    embedding, (0, self.embedding_dim - embedding.size)
                )
            return embedding.reshape(self.embedding_dim)
        except Exception as e:
            logger.error(f"Error reshaping embedding: {str(e)}")
            return np.zeros(self.embedding_dim)

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string"""
        try:
            encoded_input = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(self.device)
            with torch.no_grad():
                model_output = self.model(**encoded_input)
            embedding = self._mean_pooling(model_output, encoded_input["attention_mask"])
            embedding_np = embedding[0].detach().cpu().numpy()
            embedding_np = self._reshape_embedding(embedding_np)

            if not self._validate_embedding(embedding_np):
                logger.warning(f"Invalid embedding generated for text: {text[:100]}...")
                return np.zeros(self.embedding_dim)

            return embedding_np
        except Exception as e:
            logger.error(f"Error embedding text: {str(e)}")
            return np.zeros(self.embedding_dim)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a list of texts"""
        try:
            encoded_input = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
            with torch.no_grad():
                model_output = self.model(**encoded_input)
            embeddings = self._mean_pooling(model_output, encoded_input["attention_mask"])
            embeddings_np = embeddings.detach().cpu().numpy()

            final_embeddings = []
            for i, emb in enumerate(embeddings_np):
                reshaped = self._reshape_embedding(emb)
                if self._validate_embedding(reshaped):
                    final_embeddings.append(reshaped)
                else:
                    logger.warning(f"Invalid embedding for text {i}: {texts[i][:100]}...")
                    final_embeddings.append(np.zeros(self.embedding_dim))

            return final_embeddings
        except Exception as e:
            logger.error(f"Error embedding batch: {str(e)}")
            return [np.zeros(self.embedding_dim) for _ in texts]

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self.embedding_dim