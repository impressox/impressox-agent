from typing import List, Dict
import numpy as np
from sentence_splitter import split_text_into_sentences
from .embedder import JinaEmbedder

class SemanticChunker:
    def __init__(self, similarity_threshold: float = 0.85):
        self.embedder = JinaEmbedder()
        self.similarity_threshold = similarity_threshold

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def _merge_similar_sentences(self, sentences: List[str], embeddings: List[np.ndarray]) -> List[str]:
        """Merge sentences that are semantically similar"""
        if not sentences:
            return []

        chunks = []
        current_chunk = [sentences[0]]
        current_embedding = embeddings[0]

        for i in range(1, len(sentences)):
            similarity = self._cosine_similarity(current_embedding, embeddings[i])
            
            if similarity >= self.similarity_threshold:
                current_chunk.append(sentences[i])
                # Update current embedding as average of all sentences in chunk
                current_embedding = np.mean([embeddings[j] for j in range(i - len(current_chunk) + 1, i + 1)], axis=0)
            else:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[i]]
                current_embedding = embeddings[i]

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def chunk_text(self, text: str) -> List[str]:
        """Split text into semantic chunks"""
        # Split text into sentences
        sentences = split_text_into_sentences(text)
        
        if not sentences:
            return []

        # Get embeddings for all sentences
        embeddings = [self.embedder.embed_text(sentence) for sentence in sentences]
        
        # Merge similar sentences into chunks
        chunks = self._merge_similar_sentences(sentences, embeddings)
        
        return chunks

    def chunk_with_metadata(self, text: str, metadata: Dict) -> List[Dict]:
        """Split text into chunks and attach metadata to each chunk"""
        chunks = self.chunk_text(text)
        return [
            {
                "text": chunk,
                "metadata": metadata
            }
            for chunk in chunks
        ] 