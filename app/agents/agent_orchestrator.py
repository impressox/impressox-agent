from functools import partial
from copy import deepcopy, copy

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from app.state.agent import AgentState
from app.configs import config
from app.constants import NodeName
from app.agents.agent_factory import agent_factory
from app.utils.router_utils import router_utils
from app.cache.check_point import get_memory_saver

# Checkpoint memory
memory = get_memory_saver()


def agent_orchestrator_node(state: AgentState, config: RunnableConfig):
    """
    Node điều phối: nếu AI đã trả lời, kết thúc. Ngược lại, gọi router.
    """
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.content:
        return Command(goto=END, update={"next": END})

    goto = router_utils.router_agent(state)
    return Command(goto=goto, update={"next": goto, "current": goto})


async def generic_node(state: AgentState, node_name: str, config: RunnableConfig):
    """
    Node xử lý chung cho các agent tùy theo node_name.

    - Lọc các tin nhắn liên quan node
    - Gọi graph tương ứng từ agent_factory
    - Gắn lại name vào message trả về
    """
    # Lọc lại message dành riêng cho node
    node_state = deepcopy(state)
    node_state["messages"] = [
        msg for msg in state["messages"]
        if not (
            (isinstance(msg, AIMessage) and not msg.content and msg.name != node_name) or
            (isinstance(msg, ToolMessage) and msg.name != node_name)
        )
    ]

    # Tạo agent và lấy graph
    agent = agent_factory.create(node_name, config=config, use_cache=True)
    graph = agent.get_graph()
    if not graph:
        raise RuntimeError(f"Graph not found for node {node_name}")

    results = await graph.ainvoke(node_state)
    new_messages = results["messages"][len(node_state["messages"]):]

    # Cập nhật state
    new_state = deepcopy(state)
    new_state["node_name"] = node_name
    new_state["messages"] = state["messages"] + [copy(msg) for msg in new_messages]

    for msg in new_state["messages"][-len(new_messages):]:
        msg.name = node_name

    return new_state

# === Build StateGraph ===

builder = StateGraph(AgentState)
builder.add_edge(START, "agent_orchestrator")
builder.add_node("agent_orchestrator", agent_orchestrator_node)

# Đăng ký các node trong NodeName
for k, v in NodeName.__dict__.items():
    if not k.startswith('__') and isinstance(v, str):
        builder.add_node(v, partial(generic_node, node_name=v))

graph = builder.compile(checkpointer=memory)