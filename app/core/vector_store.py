import os
from typing import List, Dict, Optional
from chromadb import Client, Settings
from chromadb.config import Settings as ChromaSettings
from app.configs.config import app_configs

class VectorStoreManager:
    _instance = None
    _client = None
    _collection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize ChromaDB client and collection."""
        try:
            # Get config from YAML
            config = app_configs.get_vector_store_config()
            connection = config["connection"]
            settings = config["settings"]

            # Create persist directory if it doesn't exist
            persist_dir = connection["persist_directory"]
            os.makedirs(persist_dir, exist_ok=True)

            # Initialize ChromaDB client with settings
            self._client = Client(ChromaSettings(
                anonymized_telemetry=settings["anonymized_telemetry"],
                allow_reset=settings["allow_reset"],
                is_persistent=settings["is_persistent"],
                persist_directory=persist_dir
            ))

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=connection["collection_name"],
                metadata={"hnsw:space": settings["hnsw"]["space"]},
                hnsw_config=settings["hnsw"]
            )

        except Exception as e:
            print(f"Error initializing VectorStoreManager: {str(e)}")
            raise

    def search(self, query: str, n_results: int = 5, where: Optional[Dict] = None) -> List[Dict]:
        """Search for similar documents."""
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            print(f"Error searching vector store: {str(e)}")
            return []

    def get_by_source(self, source: str, limit: int = 100) -> List[Dict]:
        """Get documents by source."""
        try:
            results = self._collection.get(
                where={"source": source},
                limit=limit
            )
            return results
        except Exception as e:
            print(f"Error getting documents by source: {str(e)}")
            return []

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        try:
            count = self._collection.count()
            return {
                "total_documents": count,
                "persist_directory": app_configs.get_vector_store_config()["connection"]["persist_directory"]
            }
        except Exception as e:
            print(f"Error getting collection stats: {str(e)}")
            return {"total_documents": 0, "persist_directory": None} 