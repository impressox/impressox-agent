from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np
import os
import uuid
from workers.rag_processor.common.embedder import JinaEmbedder
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class VectorStore:
    def __init__(self):
        """Initialize Qdrant client and embedding model"""
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", "6333"))
        self.api_key = os.getenv("QDRANT_API_KEY", None)
        self.collection_name = "rag_data"

        # Initialize embedding model
        self.embedder = JinaEmbedder()
        embedding_dim = self.embedder.get_embedding_dimension()

        # Initialize Qdrant client
        self.client = QdrantClient(
            url=f"http://{self.host}:{self.port}",
            api_key=self.api_key
        )

        # Create collection if it doesn't exist
        if self.collection_name not in [c.name for c in self.client.get_collections().collections]:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=embedding_dim,  # Use dimension from Jina model
                    distance=Distance.COSINE
                )
            )

            self.client.create_payload_index(
                collection_name="rag_data",
                field_name="timestamp",
                field_schema="integer"
            )

        self.client.delete_payload_index(
            collection_name="rag_data",
            field_name="post_id"
        )

        self.client.create_payload_index(
            collection_name="rag_data",
            field_name="post_id",
            field_schema="integer"
        )

    def add_documents(self, documents: List[Dict]):
        """Add documents to the vector store"""
        if not documents:
            return

        try:
            texts = [doc["text"] for doc in documents]
            metadatas = [doc["metadata"] for doc in documents]

            # Generate embeddings using the model
            vectors = self.embedder.embed_batch(texts)

            points = [
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, text)),
                    vector=vector,
                    payload={**metadata, "text": text}
                )
                for vector, metadata, text in zip(vectors, metadatas, texts)
            ]

            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            print(f"Successfully added {len(points)} documents to Qdrant")

        except Exception as e:
            print(f"Error adding documents: {str(e)}")
            raise

    def get_by_source(self, source: str, limit: int = 100) -> List[Dict]:
        """Get documents by source"""
        try:
            result, _ = self.client.scroll(
                collection_name=self.collection_name,
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
                for point in result
            ]
        except Exception as e:
            print(f"Error getting documents by source: {str(e)}")
            return []

    def delete_by_source(self, source: str):
        """Delete all documents from a specific source"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=source))]
                )
            )
            print(f"Successfully deleted all documents from source: {source}")
        except Exception as e:
            print(f"Error deleting documents by source: {str(e)}")

    def get_collection_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "total_documents": info.points_count,
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance
            }
        except Exception as e:
            print(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}
