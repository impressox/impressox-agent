from app.constants import subgraph_mapping

# Build agent list
agent_names = list(subgraph_mapping.keys())
agent_list_str = str(agent_names)

# Format agent descriptions
agent_descriptions = "\n".join(
    f"{name}: {info['description']}"
    for name, info in subgraph_mapping.items()
)

# Construct router prompt
router_prompt = f"""Your task is to analyze the following conversation history and determine which agent should handle the user's next message. 
Return exactly one agent ID from the list below, without any explanation or extra output.

Valid agent choices: {agent_list_str}

Descriptions of each agent:
{agent_descriptions}

Conversation history:
{{chat_history}}

Return only one valid agent ID from the list {agent_list_str}. Do NOT explain or add any commentary.
"""
