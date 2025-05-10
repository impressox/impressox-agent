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

class JinaEmbedder:
    def __init__(self):
        """Initialize Jina Embeddings V3 model"""
        self.model_name = "jinaai/jina-embeddings-v3"
        # Get Hugging Face token from environment variable
        self.hf_token = os.getenv('HUGGINGFACE_TOKEN')
        if not self.hf_token:
            raise ValueError("HUGGINGFACE_TOKEN environment variable is not set")
            
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                token=self.hf_token
            )
            self.model = AutoModel.from_pretrained(
                self.model_name,
                token=self.hf_token,
                trust_remote_code=True
            )
            self.model.eval()  # Set to evaluation mode
            
            # Get embedding dimension from model config
            self.embedding_dim = self.model.config.hidden_size
            logger.info(f"Initialized JinaEmbedder with dimension {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Error initializing JinaEmbedder: {str(e)}")
            raise

    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling - take attention mask into account for correct averaging"""
        try:
            token_embeddings = model_output[0]  # Shape: (batch_size, sequence_length, hidden_size)
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            
            # Calculate mean pooling
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 0)
            sum_mask = torch.clamp(input_mask_expanded.sum(0), min=1e-9)
            mean_embeddings = sum_embeddings / sum_mask
            
            # Ensure output is 1D
            if len(mean_embeddings.shape) > 1:
                mean_embeddings = mean_embeddings.squeeze()
            
            return mean_embeddings
        except Exception as e:
            logger.error(f"Error in mean pooling: {str(e)}")
            raise

    def _validate_embedding(self, embedding: np.ndarray) -> bool:
        """Validate embedding shape and values"""
        try:
            # Ensure embedding is 1D
            if len(embedding.shape) > 1:
                logger.warning(f"Reshaping embedding from {embedding.shape} to ({self.embedding_dim},)")
                embedding = embedding.reshape(self.embedding_dim)
            
            if embedding.shape != (self.embedding_dim,):
                logger.error(f"Invalid embedding shape: {embedding.shape}, expected ({self.embedding_dim},)")
                return False
            if np.isnan(embedding).any() or np.isinf(embedding).any():
                logger.error("Embedding contains NaN or Inf values")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating embedding: {str(e)}")
            return False

    def _reshape_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """Reshape embedding to correct dimension"""
        try:
            if len(embedding.shape) > 1:
                # If 2D, take mean along first dimension
                embedding = np.mean(embedding, axis=0)
            
            # Ensure correct size
            if embedding.size != self.embedding_dim:
                logger.warning(f"Resizing embedding from {embedding.size} to {self.embedding_dim}")
                if embedding.size > self.embedding_dim:
                    # Truncate if too large
                    embedding = embedding[:self.embedding_dim]
                else:
                    # Pad with zeros if too small
                    padding = np.zeros(self.embedding_dim - embedding.size)
                    embedding = np.concatenate([embedding, padding])
            
            return embedding.reshape(self.embedding_dim)
        except Exception as e:
            logger.error(f"Error reshaping embedding: {str(e)}")
            return np.zeros(self.embedding_dim)

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string"""
        try:
            # Tokenize sentences
            encoded_input = self.tokenizer(text, padding=True, truncation=True, return_tensors='pt')
            
            # Compute token embeddings
            with torch.no_grad():
                model_output = self.model(**encoded_input)
            
            # Perform pooling
            embedding = self._mean_pooling(model_output, encoded_input['attention_mask'])
            embedding_np = embedding.numpy()
            
            # Reshape to correct dimension
            embedding_np = self._reshape_embedding(embedding_np)
            
            # Validate embedding
            if not self._validate_embedding(embedding_np):
                logger.warning(f"Invalid embedding generated for text: {text[:100]}...")
                # Return zero vector as fallback
                return np.zeros(self.embedding_dim)
            
            return embedding_np
        except Exception as e:
            logger.error(f"Error embedding text: {str(e)}")
            # Return zero vector as fallback
            return np.zeros(self.embedding_dim)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a batch of texts"""
        try:
            # Tokenize sentences
            encoded_input = self.tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
            
            # Compute token embeddings
            with torch.no_grad():
                model_output = self.model(**encoded_input)
            
            # Perform pooling
            embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
            
            # Convert to numpy and validate
            embeddings_np = [emb.numpy() for emb in embeddings]
            valid_embeddings = []
            
            for i, emb in enumerate(embeddings_np):
                # Reshape to correct dimension
                emb = self._reshape_embedding(emb)
                
                if self._validate_embedding(emb):
                    valid_embeddings.append(emb)
                else:
                    logger.warning(f"Invalid embedding generated for text {i}: {texts[i][:100]}...")
                    valid_embeddings.append(np.zeros(self.embedding_dim))
            
            return valid_embeddings
        except Exception as e:
            logger.error(f"Error embedding batch: {str(e)}")
            # Return zero vectors as fallback
            return [np.zeros(self.embedding_dim) for _ in texts]

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self.embedding_dim 