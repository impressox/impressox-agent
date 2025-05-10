from typing import List, Dict
import numpy as np
import logging
from sentence_splitter import split_text_into_sentences
from workers.rag_processor.common.embedder import JinaEmbedder

# Configure logging
logger = logging.getLogger(__name__)

class SemanticChunker:
    def __init__(self, similarity_threshold: float = 0.85, language: str = 'en'):
        self.embedder = JinaEmbedder()
        self.similarity_threshold = similarity_threshold
        self.language = language
        self.embedding_dim = self.embedder.get_embedding_dimension()
        logger.info(f"SemanticChunker initialized with language={language}, embedding_dim={self.embedding_dim}")

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            # Ensure vectors are 1D and have correct dimension
            vec1 = vec1.flatten()
            vec2 = vec2.flatten()
            
            # If vectors have wrong dimension, pad or truncate to correct size
            if vec1.shape[0] != self.embedding_dim:
                logger.warning(f"Vector 1 has wrong dimension: {vec1.shape}, expected {self.embedding_dim}")
                if vec1.shape[0] > self.embedding_dim:
                    vec1 = vec1[:self.embedding_dim]
                else:
                    vec1 = np.pad(vec1, (0, self.embedding_dim - vec1.shape[0]))
            
            if vec2.shape[0] != self.embedding_dim:
                logger.warning(f"Vector 2 has wrong dimension: {vec2.shape}, expected {self.embedding_dim}")
                if vec2.shape[0] > self.embedding_dim:
                    vec2 = vec2[:self.embedding_dim]
                else:
                    vec2 = np.pad(vec2, (0, self.embedding_dim - vec2.shape[0]))
            
            return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0

    def _merge_similar_sentences(self, sentences: List[str], embeddings: List[np.ndarray]) -> List[str]:
        """Merge sentences that are semantically similar"""
        if not sentences:
            return []

        try:
            chunks = []
            current_chunk = [sentences[0]]
            current_embedding = embeddings[0].flatten()

            for i in range(1, len(sentences)):
                next_embedding = embeddings[i].flatten()
                
                # Calculate similarity with current chunk
                similarity = self._cosine_similarity(current_embedding, next_embedding)
                logger.debug(f"Similarity between chunk and sentence {i}: {similarity}")
                
                if similarity >= self.similarity_threshold:
                    current_chunk.append(sentences[i])
                    # Update current embedding as average of all sentences in chunk
                    chunk_embeddings = [emb.flatten() for emb in embeddings[i - len(current_chunk) + 1:i + 1]]
                    current_embedding = np.mean(chunk_embeddings, axis=0)
                else:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = [sentences[i]]
                    current_embedding = next_embedding

            if current_chunk:
                chunks.append(" ".join(current_chunk))

            return chunks
        except Exception as e:
            logger.error(f"Error merging sentences: {str(e)}")
            # Return original sentences if merging fails
            return sentences

    def chunk_text(self, text: str) -> List[str]:
        """Split text into semantic chunks"""
        try:
            # Split text into sentences
            sentences = split_text_into_sentences(text, language=self.language)
            logger.debug(f"Split text into {len(sentences)} sentences")
            
            if not sentences:
                return []

            # Get embeddings for all sentences
            embeddings = []
            for i, sentence in enumerate(sentences):
                try:
                    embedding = self.embedder.embed_text(sentence)
                    # Ensure embedding has correct dimension
                    if embedding.shape[0] != self.embedding_dim:
                        logger.warning(f"Embedding for sentence {i} has wrong dimension: {embedding.shape}, expected {self.embedding_dim}")
                        if embedding.shape[0] > self.embedding_dim:
                            embedding = embedding[:self.embedding_dim]
                        else:
                            embedding = np.pad(embedding, (0, self.embedding_dim - embedding.shape[0]))
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"Error embedding sentence {i}: {str(e)}")
                    # Use zero vector as fallback
                    embeddings.append(np.zeros(self.embedding_dim))
            
            # Merge similar sentences into chunks
            chunks = self._merge_similar_sentences(sentences, embeddings)
            logger.debug(f"Created {len(chunks)} chunks")
            
            return chunks
        except Exception as e:
            logger.error(f"Error chunking text: {str(e)}")
            return [text]  # Return original text as single chunk if chunking fails

    def chunk_with_metadata(self, text: str, metadata: Dict) -> List[Dict]:
        """Split text into chunks and attach metadata to each chunk"""
        try:
            chunks = self.chunk_text(text)
            return [
                {
                    "text": chunk,
                    "metadata": metadata
                }
                for chunk in chunks
            ]
        except Exception as e:
            logger.error(f"Error chunking with metadata: {str(e)}")
            return [{"text": text, "metadata": metadata}] 