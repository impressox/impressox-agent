import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class VectorStore:
    def __init__(self, persist_directory: str = None):
        """Initialize ChromaDB client"""
        # Get persist directory from env or use default
        self.persist_directory = persist_directory or os.getenv('CHROMA_PERSIST_DIR', 'chroma_db')
        
        # Ensure directory exists
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Initialize client with settings
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True
            )
        )
        
        # Get or create collection with proper settings
        self.collection = self.client.get_or_create_collection(
            name="rag_data",
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 100,
                "hnsw:search_ef": 100
            }
        )

    def add_documents(self, documents: List[Dict]):
        """Add documents to the vector store"""
        if not documents:
            return

        try:
            # Generate unique IDs with timestamp and index
            ids = [f"doc_{datetime.now().timestamp()}_{i}" for i in range(len(documents))]
            texts = [doc["text"] for doc in documents]
            metadatas = [doc["metadata"] for doc in documents]

            # Add documents in batches if needed
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i + batch_size]
                batch_texts = texts[i:i + batch_size]
                batch_metadatas = metadatas[i:i + batch_size]
                
                self.collection.add(
                    ids=batch_ids,
                    documents=batch_texts,
                    metadatas=batch_metadatas
                )
                
            print(f"Successfully added {len(documents)} documents to vector store")
            
        except Exception as e:
            print(f"Error adding documents to vector store: {str(e)}")
            raise

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> List[Dict]:
        """Search for similar documents"""
        try:
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
        except Exception as e:
            print(f"Error searching vector store: {str(e)}")
            return []

    def get_by_source(self, source: str, limit: int = 100) -> List[Dict]:
        """Get documents by source"""
        try:
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
        except Exception as e:
            print(f"Error getting documents by source: {str(e)}")
            return []

    def delete_by_source(self, source: str):
        """Delete all documents from a specific source"""
        try:
            self.collection.delete(
                where={"source": source}
            )
            print(f"Successfully deleted all documents from source: {source}")
        except Exception as e:
            print(f"Error deleting documents by source: {str(e)}")

    def get_collection_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            print(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)} 