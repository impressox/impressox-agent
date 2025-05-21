from typing import Dict, List, Optional
from langchain_core.tools import tool
from app.core.tool_registry import register_tool
from app.constants import NodeName
from app.core.vector_store import VectorStoreManager
from app.core.mongo_search import MongoSearch
import logging
logger = logging.getLogger("uvicorn.error")

async def search_knowledge(query: str, top_k: int = 10, source: Optional[str] = "twitter", days_ago: int = 0, min_likes: int = 0, min_reposts: int = 0) -> Dict:
    """
    Search for relevant knowledge from vector store and MongoDB based on user query
    
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
        vector_results = vector_store.search(
            query=query,
            n_results=top_k,
            where=where
        )
        
        # Get MongoDB search instance
        mongo_search = await MongoSearch.get_instance()

        logger.info(f"Searching MongoDB for query: {query}")
        # Search MongoDB
        mongo_results = await mongo_search.search_binance(
            query=query,
            top_k=top_k,
            days_ago=days_ago,
            min_likes=min_likes,
            min_reposts=min_reposts
        )
        logger.info(f"MongoDB search results: {mongo_results}")
        
        # Format vector store results
        formatted_vector_results = []
        if vector_results and len(vector_results) > 0:
            for doc in vector_results:
                formatted_vector_results.append({
                    "content": doc.get("text", ""),
                    "metadata": doc.get("metadata", {}),
                    "relevance_score": 1.0 - doc.get("distance", 0.0)  # Convert distance to similarity score
                })
        
        # Combine results
        all_results = []
        
        # Add vector store results
        all_results.extend(formatted_vector_results)
        
        # Add MongoDB results if successful
        if mongo_results.get("success", False):
            all_results.extend(mongo_results["data"]["results"])
        
        # Sort by relevance score and remove duplicates
        seen_contents = set()
        unique_results = []
        for result in sorted(all_results, key=lambda x: x["relevance_score"], reverse=True):
            content = result["content"]
            if content not in seen_contents:
                seen_contents.add(content)
                unique_results.append(result)
                if len(unique_results) >= top_k:
                    break
            
        return {
            "success": True,
            "data": {
                "results": unique_results,
                "query": query,
                "total_results": len(unique_results)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error searching knowledge: {str(e)}"
        }

@register_tool(NodeName.GENERAL_NODE, "search_binance_knowledge")
@tool
async def search_binance_knowledge() -> Dict:
    """
    Tra cứu và cung cấp nhanh tất cả các thông tin liên quan đến hệ sinh thái Binance:
    - Tổng quan về Binance và các sản phẩm/dịch vụ của Binance (như Binance Earn, Launchpad, Futures…)
    - Thông tin chi tiết về Binance Alpha, bao gồm cách tham gia, hướng dẫn tính điểm Binance Alpha, các chương trình thưởng và quy đổi điểm.
    - Tin tức, cập nhật mới nhất từ Binance, phân tích các dự án do Binance phát hành hoặc hỗ trợ.
    - Các tài liệu, hướng dẫn chính thức từ Binance (có trích dẫn nguồn).

    ✅ Dùng khi:
    - Người dùng hỏi bất kỳ vấn đề nào về Binance, các sản phẩm/dịch vụ hoặc chương trình mới của Binance.
    - Người dùng cần giải thích về Binance Alpha, quy chế, cách tính hoặc sử dụng điểm Binance Alpha.
    - Cần cập nhật tin tức, sự kiện mới nhất liên quan đến Binance và các dự án trong hệ sinh thái Binance.
    - Muốn trích dẫn nguồn chính thống từ Binance để lập luận, giải thích hoặc cung cấp bối cảnh.
    """
     # Get MongoDB search instance
    mongo_search = await MongoSearch.get_instance()
    return await mongo_search.search_binance_knowledge() 

@register_tool(NodeName.GENERAL_NODE, "search_x_binance")
@tool
async def search_x_binance(query: str, top_k: Optional[int] = 10, source: Optional[str] = None, days_ago: int = 0, min_likes: int = 0, min_reposts: int = 0) -> Dict:
    """
    Tra cứu nhanh thông tin về binance trên X (Twitter)

    ✅ Dùng khi:
    - User hỏi về diễn biến mới nhất liên quan đến binance trên X (Twitter)
    - Cần tìm lại tweet đã nhúng có liên quan đến binance trên X (Twitter)
    - Muốn trích dẫn nguồn tweet để hỗ trợ lập luận hoặc hiểu thêm bối cảnh.

    Args:
        query (str): Câu hỏi hoặc từ khóa tìm kiếm
        top_k (int, optional): Số lượng kết quả trả về. Mặc định là 10.
        source (str, optional): Nguồn dữ liệu cần tìm kiếm ('twitter' hoặc 'telegram'). Mặc định là tìm tất cả nguồn.
        days_ago (int, optional): Số ngày gần đây nhất để tìm kiếm. Mặc định là 0.
        min_likes (int, optional): Số lượng likes tối thiểu. Mặc định là 0.
        min_reposts (int, optional): Số lượng reposts tối thiểu. Mặc định là 0.
        
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

    return await search_knowledge(query, top_k, source, days_ago, min_likes, min_reposts) 
