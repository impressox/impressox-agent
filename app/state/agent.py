from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.managed import IsLastStep, RemainingSteps
from typing_extensions import Annotated
from pydantic import BaseModel
from typing import TypedDict, Sequence, Union

StructuredResponse = Union[dict, BaseModel]
class AgentState(TypedDict):
    """The state of the agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]

    is_last_step: IsLastStep

    remaining_steps: RemainingSteps

    structured_response: StructuredResponse
    
    next: str
    
    current: str = None