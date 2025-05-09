from app.configs import app_configs
from app.utils.call_api import call_api
from app.core.tool_registry import register_tool
from app.constants import NodeName
from langchain_core.tools import tool
import asyncio

@register_tool(NodeName.GENERAL_NODE, "summary_social")
@tool
def get_social_summary() -> dict:
    """
        Tóm tắt các chủ đề đang được thảo luận nhiều trên mạng xã hội X (Twitter).

        - Dữ liệu đầu vào: Không cần đầu vào cụ thể.
        - Trả về: {success: bool, data: [...summary...], error: "..."}
        - Mỗi bản tóm tắt có thể chứa thông tin về token, meme, trend hoặc FUD nổi bật gần đây.

        🎯 **Khi nào nên dùng tool này?**
        - Khi người dùng hỏi: "Có gì đang hot trên Twitter hôm nay?"
        - Hoặc các câu như:
            - “Có token nào đang được bàn tán nhiều không?”
            - “Trend nào đang lên trên mạng xã hội?”
        - Luôn đi kèm với phân tích ngắn gọn về các chủ đề nổi bật, ví dụ như: "Meme này đang hot vì lý do gì?", "Có tin gì mới về token này không?", "Có FUD nào đáng chú ý không?".
        - Đảm bảo rằng các thông tin này được trình bày một cách rõ ràng và dễ hiểu.
    """
    try:
        api_conf = app_configs.API_CONF["summary_social"]
        url = api_conf["url"]
        timeout = api_conf.get("timeout", 30)
        resp = asyncio.run(call_api(url, data={}, method="POST", timeout=timeout))
        return resp
    except Exception as e:
        return {"success": False, "error": str(e)}
