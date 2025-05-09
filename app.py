import streamlit as st
st.set_page_config(layout="wide", page_title="Agent Chat", page_icon="🤖")

import time
import asyncio
import json
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from pymongo import MongoClient
from langfuse.callback import CallbackHandler
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit import runtime

from app.utils.time_util import get_current_time, get_this_week_time
from app.agents.agent_orchestrator import graph
from app.configs import app_configs

# ========== MongoDB ==========
@st.cache_resource
def connect_mongo():
    mongo_config = app_configs.get_mongo_config()
    client = MongoClient(
        mongo_config["connection"]["url"],
        connect=False,
    )
    return client["Agent-Langgraph"]

mongo_db = connect_mongo()

# ========== Page Config ==========
st.title("Chat with Agent")
st.button("Clear message", on_click=lambda: st.session_state.clear())

# ========== Get Remote IP (Optional) ==========
def get_remote_ip() -> str:
    try:
        ctx = get_script_run_ctx()
        if ctx:
            session_info = runtime.get_instance().get_client(ctx.session_id)
            return session_info.request.remote_ip if session_info else None
    except:
        pass
    return None

# ========== Init Session State ==========
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "config" not in st.session_state:
    current_time = get_current_time()
    week_time = get_this_week_time()
    langfuse_config = app_configs.get_langfuse_config()
    langfuse_handler = CallbackHandler(
        secret_key=langfuse_config["secret_key"],
        public_key=langfuse_config["public_key"],
        host=langfuse_config["host"],
    )
    st.session_state.config = {
        "configurable": {
            "env": "test",
            "app": "AGENTCORE",
            "user_id": "Guest",
            "user_name": "Guest",
            "gender": "Male",
            "x_birthdate": "01/01/2000",
            "response_markdown": True,
            "message_id": "",
            "version": 4,
            "language": "",
            "this_monday": week_time["monday"],
            "this_sunday": week_time["sunday"],
            "current_time": current_time,
            "thread_id": st.session_state.session_id,
        },
        "callbacks": [langfuse_handler],
        "recursion_limit": 15
    }

# ========== Config UI ==========
with st.expander("Config"):
    config = st.session_state.config["configurable"]
    col1, col2, col3 = st.columns(3)
    config["user_name"] = col1.text_input("User Name", value=config["user_name"])
    config["gender"] = col2.text_input("Gender", value=config["gender"])
    config["x_birthdate"] = col3.text_input("Date of Birth", value=config["x_birthdate"])

    if st.button("Submit Config"):
        session_id = str(uuid4())
        st.session_state.session_id = session_id
        
        st.session_state.config = {
            "configurable": config
        }

# ========== Process Events ==========
async def process_events(inputs: dict) -> AsyncGenerator[str, None]:
    async for event in graph.astream_events(inputs, config=st.session_state.config, version="v1"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield content

            usage_metadata = event["data"]["chunk"].usage_metadata
            if usage_metadata:
                input_tokens = usage_metadata["input_tokens"]
                output_tokens = usage_metadata["output_tokens"]
                model = event["metadata"]["ls_model_name"]

                if "gpt-4o-2024-08-06" in model:
                    price = ((input_tokens / 1e6) * 2.5) + ((output_tokens / 1e6) * 10)
                else:
                    price = ((input_tokens / 1e6) * 0.15) + ((output_tokens / 1e6) * 0.6)

                vnd = round(price * 26060.00, 2)
                yield f"\n\n**Tokens**: {input_tokens} in / {output_tokens} out\n**Cost**: ${round(price, 6)} ~ {vnd} VND\n\n"

        elif kind == "on_tool_start":
            tool_name = event["name"]
            tool_input = event["data"].get("input", {})
            output = f"\n\n➡️ Tool `{tool_name}` called\n\n"
            
            if tool_input:  # Only add content if input is not empty
                # Format tool input consistently
                if isinstance(tool_input, str):
                    formatted_input = tool_input
                else:
                    try:
                        formatted_input = json.dumps(tool_input, indent=2, ensure_ascii=False, default=str)
                    except:
                        formatted_input = str(tool_input)
                
                output += f" with:\n```\n{formatted_input}\n```"
            
            yield output

        elif kind == "on_tool_end":
            pass

# ========== Async to Sync Generator ==========
def to_sync_generator(async_func, *args, **kwargs):
    async_gen = async_func(*args, **kwargs)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        while True:
            try:
                yield loop.run_until_complete(anext(async_gen))
            except StopAsyncIteration:
                break
    finally:
        loop.close()

# ========== Show Chat History ==========
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], dict):
            st.json(message["content"])
        else:
            st.markdown(message["content"], unsafe_allow_html=True)

# ========== Chat Input ==========
if prompt := st.chat_input("What is up?", max_chars=1000):
    inputs = {"messages": [("user", prompt)]}
    if not st.session_state["messages"]:
        mongo_db["conversations"].insert_one({
            "session_id": st.session_state["session_id"],
            "messages": [],
            "created_at": datetime.now().astimezone(timezone(timedelta(hours=7))).isoformat()
        })

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        start_time = time.time()
        response = st.write_stream(to_sync_generator(process_events, inputs))
        end_time = time.time() - start_time

        response_id = uuid4().hex
        st.write(f"⏱️ **Processed in**: {round(end_time, 2)}s")
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "id": response_id,
            "stars": 0
        })

        mongo_db["conversations"].update_one(
            {"session_id": st.session_state["session_id"]},
            {
                "$push": {
                    "messages": {
                        "message_id": response_id,
                        "user": prompt,
                        "assistant": response,
                        "stars": 0,
                        "feedback_message": "",
                        "created_at": datetime.now().astimezone(timezone(timedelta(hours=7))).isoformat()
                    }
                }
            }
        )
