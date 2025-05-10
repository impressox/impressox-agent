from typing import Dict, List, Optional
from langchain_core.tools import tool
from app.core.tool_registry import register_tool
from app.constants import NodeName
from app.core.vector_store import VectorStoreManager

async def search_knowledge(query: str, top_k: int = 3, source: Optional[str] = "twitter") -> Dict:
    """
    Search for relevant knowledge from vector store based on user query
    
    Args:
        query (str): The search query from user
        top_k (int): Number of most relevant documents to return
        source (str, optional): Filter by source (e.g., 'twitter', 'telegram'). Defaults to 'twitter'
        
    Returns:
        Dict containing search results and metadata
    """
    try:
        # Get vector store manager instance
        vector_store = VectorStoreManager()
        
        # Build where conditions
        where = {"source": source}
        
        # Search vector store
        results = vector_store.search(
            query=query,
            n_results=top_k,
            where=where
        )
        
        # Format results
        formatted_results = []
        if results and len(results) > 0:
            for doc in results:
                formatted_results.append({
                    "content": doc.get("text", ""),
                    "metadata": doc.get("metadata", {}),
                    "relevance_score": 1.0 - doc.get("distance", 0.0)  # Convert distance to similarity score
                })
            
        return {
            "success": True,
            "data": {
                "results": formatted_results,
                "query": query,
                "total_results": len(formatted_results)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error searching knowledge: {str(e)}"
        }

@register_tool(NodeName.GENERAL_NODE, "search_knowledge")
@tool
async def search_knowledge_tool(query: str, top_k: Optional[int] = 10, source: Optional[str] = None) -> Dict:
    """
    Tra cứu nhanh thông tin, tin tức, hoặc quan điểm của các KOL, dự án crypto trên X (Twitter).

    ✅ Dùng khi:
    - User hỏi về diễn biến mới nhất liên quan đến Binance, Elon Musk, các nhân vật nổi tiếng, hoặc trend trên crypto Twitter.
    - Cần tìm lại tweet đã nhúng có liên quan đến một dự án, token, hoặc chủ đề cụ thể.
    - Muốn trích dẫn nguồn tweet để hỗ trợ lập luận hoặc hiểu thêm bối cảnh.

    Args:
        query (str): Câu hỏi hoặc từ khóa tìm kiếm
        top_k (int, optional): Số lượng kết quả trả về. Mặc định là 10.
        source (str, optional): Nguồn dữ liệu cần tìm kiếm ('twitter' hoặc 'telegram'). Mặc định là tìm tất cả nguồn.
        
    Returns:
        Dict chứa kết quả tìm kiếm và metadata:
        {
            "success": bool,
            "data": {
                "results": [
                    {
                        "content": str,
                        "metadata": dict,
                        "relevance_score": float
                    }
                ],
                "query": str,
                "total_results": int
            }
            hoặc
            "error": str
        }
    """
    return await search_knowledge(query, top_k, source) 