import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
from typing import List, Union

class JinaEmbedder:
    def __init__(self):
        """Initialize Jina Embeddings V3 model"""
        self.model_name = "jinaai/jina-embedding-v3"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.eval()  # Set to evaluation mode

    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling - take attention mask into account for correct averaging"""
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 0) / torch.clamp(input_mask_expanded.sum(0), min=1e-9)

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string"""
        # Tokenize sentences
        encoded_input = self.tokenizer(text, padding=True, truncation=True, return_tensors='pt')
        
        # Compute token embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        
        # Perform pooling
        embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
        
        return embeddings.numpy()

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a batch of texts"""
        # Tokenize sentences
        encoded_input = self.tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
        
        # Compute token embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        
        # Perform pooling
        embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
        
        return [emb.numpy() for emb in embeddings]

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        # Jina Embeddings V3 produces 1024-dimensional vectors
        return 1024 