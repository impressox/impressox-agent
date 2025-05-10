import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime

class VectorStore:
    def __init__(self, persist_directory: str = "chroma_db"):
        """Initialize ChromaDB client"""
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        self.collection = self.client.get_or_create_collection(
            name="rag_data",
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, documents: List[Dict]):
        """Add documents to the vector store"""
        if not documents:
            return

        ids = [f"doc_{datetime.now().timestamp()}_{i}" for i in range(len(documents))]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> List[Dict]:
        """Search for similar documents"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            where_document=where_document
        )

        return [
            {
                "text": doc,
                "metadata": meta,
                "distance": dist
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )
        ]

    def get_by_source(self, source: str, limit: int = 100) -> List[Dict]:
        """Get documents by source"""
        results = self.collection.get(
            where={"source": source},
            limit=limit
        )

        return [
            {
                "text": doc,
                "metadata": meta
            }
            for doc, meta in zip(results["documents"], results["metadatas"])
        ]

    def delete_by_source(self, source: str):
        """Delete all documents from a specific source"""
        self.collection.delete(
            where={"source": source}
        ) 