import os
import logging
import uuid
import numpy as np
from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, Filter, FieldCondition, MatchValue
)
from app.core.embedder import Embedder
from app.configs.config import app_configs

logger = logging.getLogger(__name__)

class VectorStoreManager:
    _instance = None
    _client = None
    _collection_name = None
    _embedder = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize Qdrant client and collection."""
        try:
            config = app_configs.get_vector_store_config()
            connection = config.get("connection", {})
            settings = config.get("settings", {})
            logger.info(f"Vector store config: {config}")

            host = connection.get("host", "localhost")
            port = int(connection.get("port", 6333))
            api_key = connection.get("api_key")  # Optional

            self._collection_name = connection.get("collection_name", "rag_data")

            # Initialize embedder
            self._embedder = Embedder()
            embedding_dim = self._embedder.get_embedding_dimension()

            self._client = QdrantClient(
                url=f"http://{host}:{port}",
                api_key=api_key
            )

            # Create collection if it doesn't exist
            if self._collection_name not in [c.name for c in self._client.get_collections().collections]:
                self._client.recreate_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(
                        size=embedding_dim,
                        distance=Distance.COSINE
                    )
                )

        except Exception as e:
            logger.error(f"Error initializing VectorStoreManager: {str(e)}", exc_info=True)
            raise

    def search(self, query: str, n_results: int = 10, where: Optional[Dict] = None, prefer_recent: bool = False, score_threshold: float = 0.8) -> List[Dict]:
        """Search for similar documents.
        
        Args:
            query (str): The search query
            n_results (int): Number of results to return
            where (Dict, optional): Where conditions for filtering (e.g., {"source": "twitter"})
            order_by (str, optional): Field to order by. Can be:
                - Simple field name (e.g., "timestamp" - defaults to desc)
                - Field with order (e.g., "timestamp:desc" or "timestamp:asc")
                - Multiple fields (e.g., "timestamp:desc,score:asc")
        """
        try:
            raw_limit = max(n_results * 5, 100) if prefer_recent else n_results

            query_vector = self._embedder.embed_text(query)
            query_vector = query_vector / np.linalg.norm(query_vector)
            query_vector = query_vector.tolist()

            filter_query = None
            if where:
                filter_query = Filter(
                    must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in where.items()]
                )

            results = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_vector,
                limit=raw_limit,
                query_filter=filter_query,
                with_payload=True,
                score_threshold=score_threshold
            )

            formatted_results = [
                {
                    "text": hit.payload.get("text", ""),
                    "metadata": hit.payload,
                    "score": float(hit.score),
                    "timestamp": hit.payload.get("timestamp", 0)
                }
                for hit in results
            ]

            if prefer_recent:
                formatted_results.sort(key=lambda x: x["timestamp"], reverse=True)

            return formatted_results[:n_results]
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}", exc_info=True)
            return []
        
    def get_by_source(self, source: str, limit: int = 100) -> List[Dict]:
        """Get documents by source."""
        try:
            results, _ = self._client.scroll(
                collection_name=self._collection_name,
                limit=limit,
                filter=Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=source))]
                )
            )

            return [
                {
                    "text": point.payload.get("text", ""),
                    "metadata": point.payload
                }
                for point in results
            ]
        except Exception as e:
            logger.error(f"Error getting documents by source: {str(e)}", exc_info=True)
            return []

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        try:
            info = self._client.get_collection(collection_name=self._collection_name)
            return {
                "total_documents": info.points_count,
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}", exc_info=True)
            return {"total_documents": 0, "error": str(e)}
