#!/usr/bin/env python3
"""
Quick start script for the Grad Director AI Chatbot (LangGraph version)
"""
import os
from typing import Annotated, TypedDict

import streamlit as st
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from langchain_core.chat_history import InMemoryChatMessageHistory


# LangGraph + tools
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt.tool_node import ToolNode
from langchain_community.tools.tavily_search import TavilySearchResults

from prompt import REACT_SYSTEM_PROMPT

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Grad Director AI Chatbot",
    page_icon="",
    layout="centered"
)

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = InMemoryChatMessageHistory()

initialize_session_state()

# LangGraph state
class State(TypedDict):
    messages: Annotated[list, add_messages]

@st.cache_resource
def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY not found in .env file")
        st.info("Please create a .env file in the project root with: OPENAI_API_KEY=your_api_key_here")
        st.stop()

    # Keep model/temperature consistent with your original setup
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        openai_api_key=api_key
    )

@st.cache_resource
def get_graph():
    llm = get_llm()

    # Tavily search tool
    # Make sure TAVILY_API_KEY is set in your .env if you want search enabled
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    tool = TavilySearchResults(max_results=2) if tavily_key else None
    tools = [tool] if tool else []

    llm_with_tools = llm.bind_tools(tools) if tools else llm

    def chatbot(state: State):
        # Let the LLM decide whether to call tools
        result = llm_with_tools.invoke(state["messages"])
        return {"messages": [result]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)

    if tools:
        tool_node = ToolNode(tools=tools)
        graph_builder.add_node("tools", tool_node)
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")

    graph_builder.add_edge(START, "chatbot")
    graph = graph_builder.compile()
    return graph

def invoke_graph(all_messages):
    """
    all_messages: list of langchain_core.messages BaseMessage
    Returns the final assistant message text.
    """
    graph = get_graph()
    # Run the graph with the accumulated messages
    state = graph.invoke({"messages": all_messages})
    # Find the last assistant message
    last_ai = None
    for m in reversed(state["messages"]):
        if isinstance(m, AIMessage):
            last_ai = m
            break
    return last_ai.content if last_ai else ""

def main():

    st.title("Grad Director AI Chatbot")
    st.markdown("---")

    # Check API keys early for user guidance
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY not found in .env file")
        st.info(
            "To fix this:\n"
            "1. Create a `.env` file in the project root\n"
            "2. Add your OpenAI API key: `OPENAI_API_KEY=your_api_key_here`\n"
            "3. Get your API key from: https://platform.openai.com/api-keys"
        )
        st.stop()

    if not os.getenv("TAVILY_API_KEY"):
        st.info("Optional: set TAVILY_API_KEY in .env to enable web search.")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.chat_history = InMemoryChatMessageHistory()
            st.rerun()

    with col2:
        st.markdown(
            "Start chatting below! You can ask questions about graduate programs, "
            "admissions, requirements, and academic guidance. You can also ask about "
            "the application process, deadlines, and other relevant information."
        )

    st.markdown("---")

    chat_container = st.container()
    with chat_container:
        # Display prior messages
        if "messages" in st.session_state:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Chat input
        if user_response := st.chat_input("What would you like to know?"):
            # Add user message to visible transcript and history
            st.session_state.messages.append({"role": "user", "content": user_response})
            st.session_state.chat_history.add_message(HumanMessage(content=user_response))

            # Display user message immediately
            with st.chat_message("user"):
                st.markdown(user_response)

            with st.chat_message("assistant"):
                with st.spinner("🤔 Thinking..."):
                    try:
                        # System preamble
                        system_message = SystemMessage(
                            # content=(
                            #     "You are a helpful grad director chatbot. You help students with questions about graduate programs, admissions, requirements, and academic guidance."
                            # )
                            content = REACT_SYSTEM_PROMPT
                        )

                        # Compose full message list for the graph
                        prior_msgs = [system_message] + st.session_state.chat_history.messages
                        # Append the latest human turn explicitly to ensure it's included
                        prior_msgs.append(HumanMessage(content=user_response))

                        # Run the graph
                        ai_text = invoke_graph(prior_msgs)

                        # Display AI response
                        st.markdown(ai_text)

                        # Persist assistant message to transcript and history
                        st.session_state.messages.append({"role": "assistant", "content": ai_text})
                        st.session_state.chat_history.add_message(AIMessage(content=ai_text))

                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.info("Please check your API keys and internet connection.")

if __name__ == "__main__":
    main()